# P2 — RAG Assistant · Demo Notes

---

## The Problem

Most organisations have knowledge locked in documents — policy PDFs, product manuals, financial reports, Excel spreadsheets. The standard way to find information is to remember which document it's in, open it, and Ctrl+F. That breaks the moment you have more than a handful of documents, or when the answer spans multiple files.

Search helps, but keyword search doesn't understand meaning. If the document says "annual leave entitlement" and you search "how many days off", you get nothing. You need something that understands the question and finds the relevant passage — regardless of exact wording.

---

## The Solution

RAG — Retrieval Augmented Generation.

At ingest time: every document is split into chunks, each chunk is converted into a vector (a list of numbers that represents the semantic meaning), and stored in pgvector inside PostgreSQL.

At query time: your question is also converted into a vector, and the database finds the chunks whose vectors are most similar — that's the retrieval. Those chunks go into the LLM's context along with your question, and the LLM answers using only what's in those chunks. Citations point back to the source document so you know where the answer came from.

---

## What Makes This Different

**vs. standard tutorials (LangChain, LlamaIndex docs):**
Every RAG tutorial uses FAISS or ChromaDB — in-memory vector stores that vanish when the process exits. They're fine for demos, terrible for production. P2 uses PostgreSQL + pgvector: persistent, transactional, queryable with SQL if needed, runs in Docker. The same database that stores your business data can store your vectors.

**vs. off-the-shelf tools (Pinecone, Weaviate):**
Pinecone is a managed vector database — great in production but adds a paid external dependency and sends your data to a third party. pgvector runs in your own infrastructure, on a database you already know how to operate, back up, and secure.

**vs. other portfolio projects:**
Multi-format support (PDF, Excel, plain text) with real citation snippets — not just "Source: document.pdf" but the actual passage that was retrieved. This is the difference between a RAG that tells you it found something and one that shows you what it found.

---

## Demo Tour

### Before you start
- [ ] Docker pgvector container running on port 5432 (database `p2_rag`)
- [ ] Backend: `uvicorn main:app --port 8000` from `p2-rag-assistant/backend/`
- [ ] Frontend: `npm run dev` from `p2-rag-assistant/frontend/`
- [ ] Have a test document ready (PDF or Excel works well)

---

### Step 1 — Open the app
**Open:** `http://localhost:3000`

**Say:**
> "This is the RAG Assistant. You can upload any document — PDF, Excel, plain text — and then have a conversation with it. The system doesn't just search for keywords. It understands the meaning of your question and finds the relevant parts of the document, even if they're worded differently."

---

### Step 2 — Upload a document
**Do:** Click Upload, select a document (company_policy.pdf works well for demo).

**Say:**
> "I'm uploading a company policy document. Behind the scenes, three things are happening: the document is being split into 500-character chunks with some overlap, each chunk is being embedded — converted into a 1024-dimensional vector — and stored in PostgreSQL. This takes about 10–15 seconds for a typical document."

---

### Step 3 — Ask a question
**Do:** Once ingested, type: `"How many days of annual leave do full-time employees get?"`

**Say:**
> "Now I'm asking a natural language question. The system embeds my question into a vector, does a cosine similarity search in pgvector to find the 4 most relevant chunks, passes those chunks plus my question to the LLM, and the LLM answers using only that context. It can't hallucinate something from outside the document — it's grounded."

---

### Step 4 — Show the citations
**Do:** Point to the citation snippets below the answer.

**Say:**
> "These are the citations. Not just the filename — the actual passage that was used to generate the answer. If the answer looks off, you can read the source and decide whether the retrieval pulled the right context. This is what makes RAG auditable."

---

### Step 5 — Ask an unanswerable question
**Do:** Type: `"What is the CEO's name?"`

**Say:**
> "Now I'm asking something the document doesn't contain. A well-built RAG system should refuse rather than make something up. Watch what happens — it says 'I could not find this in the provided documents.' That refusal is intentional. The LLM is instructed to only answer from retrieved context."

---

### Step 6 — (If time) Upload a second document
**Do:** Upload a second file and ask a question that spans both.

**Say:**
> "The system handles multiple documents. Each chunk knows which document it came from, so the citations always trace back to the right source even across a mixed corpus."

---

## Code Walkthrough

### `db.py` — pgvector schema and connection
**What it does:** Creates the `documents` table with an `embedding vector(1024)` column, manages the database connection pool, and provides the `insert_chunks()` and `similarity_search()` helpers.

**Key function: `similarity_search(query_vec, top_k)`**
```python
SELECT content, source, 1 - (embedding <=> %s::vector) AS similarity
FROM documents
ORDER BY embedding <=> %s::vector
LIMIT %s
```
Plain English: The `<=>` operator is pgvector's cosine distance. `1 - distance = similarity`. The ORDER BY sorts by closeness so the top results are the most semantically similar chunks. This is the entire retrieval step in one SQL query.

---

### `ingest.py` — chunking and embedding pipeline
**What it does:** Takes an uploaded file, extracts text (using PyMuPDF for PDFs, openpyxl for Excel), splits it into overlapping chunks, calls NVIDIA's embedding model, and writes to pgvector.

**Key function: `ingest_document(file_bytes, filename)`**

Chunking strategy: 500-character chunks with 50-character overlap. The overlap prevents answers from falling in a gap between two chunks — if a sentence spans a chunk boundary, at least one chunk will contain most of it.

Embedding: one API call per chunk to `nvidia/nemotron-3-embed-1b`. Returns a 1024-dimensional vector. Stored as `vector(1024)` in PostgreSQL. At query time, your question gets the same treatment — one API call — then the SQL comparison finds the nearest chunks.

---

### `query.py` — retrieval and answer generation
**What it does:** Embeds the user's question, calls `similarity_search()`, builds a prompt with the retrieved chunks, calls the LLM, and returns the answer with citations.

**Key function: `answer(question)`**

The prompt structure is critical:
```
You are a helpful assistant. Answer ONLY using the context below.
If the answer is not in the context, say "I could not find this."

Context:
[chunk 1]
[chunk 2]
[chunk 3]
[chunk 4]

Question: {question}
```

The "answer ONLY using the context" instruction is what prevents hallucination. The LLM sees it as a hard constraint. The citation extraction pulls the `source` and first 600 characters of each retrieved chunk — enough to show the relevant passage.

---

### `main.py` — FastAPI endpoints
**What it does:** Wires up the `/ingest` and `/query` routes, handles CORS for the Next.js frontend, and manages file upload parsing.

The Next.js `next.config.ts` proxies all `/api/*` requests to `http://127.0.0.1:8000` — so the frontend calls `/api/ingest` and Next.js forwards it to the FastAPI backend. No CORS issue in the browser, no hardcoded backend URL in the UI code.

---

## New Concepts to Stress

### Vector Embeddings
An embedding is a translation of text into a point in high-dimensional space such that similar meanings end up close together. "Annual leave" and "days off work" land near each other. "Invoice total" and "annual leave" land far apart. The embedding model learns this mapping from billions of text examples.

The `<=>` operator in pgvector computes cosine distance between two vectors — how far apart they point in that high-dimensional space. Small distance = similar meaning.

### RAG vs Fine-tuning
A common question: "why not just fine-tune the LLM on your documents?" Fine-tuning bakes knowledge into model weights — expensive, can't easily update when docs change, and you can't cite where the answer came from. RAG keeps the knowledge external — update the vector store when docs change, citations come for free, no retraining. RAG is the right answer for dynamic document collections.

### Chunking Strategy
Why 500 characters with 50-character overlap? Too large a chunk and you retrieve irrelevant text along with the relevant part, confusing the LLM. Too small and you might not have enough context for a coherent answer. Overlap prevents important sentences from being split between chunks. These numbers are tunable — P3 evaluates whether they're set correctly.

---

## Conclusion

P2 builds the complete RAG pipeline from first principles — chunking, embedding, storage, retrieval, generation, citations — on production-grade infrastructure (PostgreSQL, not in-memory stores). It handles multiple document formats and teaches the LLM to refuse when it doesn't know.

**Key takeaway for the room:** RAG is not a feature you bolt on — it's a pipeline with multiple moving parts, each of which can fail independently. Understanding every step is what lets you debug it when it does.
