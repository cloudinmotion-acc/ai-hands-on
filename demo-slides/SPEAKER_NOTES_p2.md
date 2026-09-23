# P2 — RAG Assistant: Speaker Notes

Format guide:

- Regular text = what you say
- `[ EXPLAIN TO AUDIENCE ]` = pause and teach a concept before moving on
- `[ DEMO ]` = switch to screen

---

## Opening (30 seconds)

> "P2 is a classic Retrieval Augmented Generation pipeline — the most common pattern you'll see in production AI systems today. The idea is simple: instead of asking an LLM to answer from memory, you give it your own documents and ask it to answer from those. Every claim it makes is grounded in the document you uploaded."

---

## The Problem It Solves

> "LLMs hallucinate. If you ask GPT 'what is our company's leave policy', it will confidently make something up. It's not lying on purpose — it just fills gaps with plausible-sounding text. RAG solves this — the LLM only answers from context you explicitly provide, and it cites exactly which part of the document it used."

### `[ EXPLAIN TO AUDIENCE ]` — Why do LLMs hallucinate?

> "LLMs are trained to predict the next most likely word. They don't have a fact-checker inside. When they don't know something, they don't say 'I don't know' — they generate text that looks like a correct answer. RAG sidesteps this entirely: you don't ask the LLM to recall facts, you hand it the facts and ask it to read and summarize."

---

## Architecture Walkthrough

### `[ EXPLAIN TO AUDIENCE ]` — What is RAG?

> "RAG stands for Retrieval Augmented Generation. It has two halves:
>
> Retrieval — searching your document store to find relevant chunks.
> Generation — an LLM reading those chunks and writing an answer.
>
> Think of it like an open-book exam. Without RAG, the LLM is doing a closed-book exam from memory. With RAG, you put the textbook in front of it and say: answer only from this."

---

### Ingestion side (when you upload a file)

> "When you upload a document, it goes through a two-step pipeline."

### Step 1 — Chunking

> "The document is split into chunks — 500 characters each, with a 50-character overlap so context doesn't get cut off at boundaries."

### `[ EXPLAIN TO AUDIENCE ]` — What is chunking and why does it matter?

> "You can't feed an entire 50-page PDF into the LLM every time someone asks a question — it's too slow and expensive. So you break the document into small pieces. The overlap is important: if a key sentence falls at the end of one chunk, the overlap ensures it also appears at the start of the next, so it doesn't disappear from search results.
>
> Chunk size is a tuning decision. Too small = chunks lack context. Too large = you retrieve irrelevant surrounding text. 500 characters is a reasonable starting point for dense prose."

### Step 2 — Embedding

> "Each chunk is converted into a vector — a list of numbers — using NVIDIA's embedding model. That vector captures the meaning of the text, not just the keywords."

### `[ EXPLAIN TO AUDIENCE ]` — What is an embedding?

> "Imagine plotting every sentence in a 3D space where sentences with similar meaning are close together. 'How many days of leave do I get?' and 'What is the annual leave entitlement?' would land near each other even though they share no words. That's what an embedding does — it maps meaning into geometry. In practice it's not 3D, it's 1024 or more dimensions, but the principle is the same.
>
> This is how RAG finds relevant chunks without keyword matching. It finds chunks that are semantically close to your question."

### Step 3 — pgvector

> "Those vectors are stored in pgvector — PostgreSQL with a vector extension. The knowledge base is persistent across restarts."

### `[ EXPLAIN TO AUDIENCE ]` — What is a vector database?

> "A regular database stores rows and columns and lets you filter by exact values. A vector database stores embeddings and lets you search by similarity — 'give me the 5 most semantically similar documents to this query'. pgvector brings that capability into Postgres, which means you get vector search plus all the reliability and tooling of a standard relational database."

---

### Query side (when you ask a question)

> "When you ask a question, the same embedding model converts your question into a vector. We do a cosine similarity search in pgvector to find the top-K most relevant chunks."

### `[ EXPLAIN TO AUDIENCE ]` — What is cosine similarity?

> "Cosine similarity measures the angle between two vectors. If two vectors point in the same direction — angle close to zero — similarity is close to 1. If they point in completely different directions, similarity is close to 0. So a score of 0.92 means the chunk is very closely related to your question. You'll see these scores in the citation cards — they tell you how confident the retrieval step was."

> "Those top-K chunks become the context, injected into the system prompt. The LLM reads the context and answers — and we return both the answer and which chunks it came from."

### `[ EXPLAIN TO AUDIENCE ]` — What is a system prompt?

> "A prompt is the instruction you give the LLM before the conversation starts. The system prompt sets the rules: 'You are a research assistant. Only answer from the provided context. If the answer isn't there, say so.' The user's question is then added on top of that. The LLM sees both and generates its answer.
>
> We have two prompt versions — V1 is strict and refuses anything not in the document. V2 is more charitable and interprets indirect questions helpfully."

---

## Key Technical Decisions

### Why pgvector over FAISS?

> "FAISS is in-memory and disappears on restart. pgvector is persistent, lives in Postgres, can be queried with SQL, and scales to production. For a demo this size it's overkill — but it shows production thinking."

### Why ChatOpenAI with NVIDIA base URL instead of ChatNVIDIA?

> "LangChain's ChatNVIDIA wrapper threw constant warnings about non-default parameters like temperature and frequency_penalty. ChatOpenAI with a custom base_url is OpenAI-compatible and treats those as native params. No warnings, cleaner code."

### Why two prompt versions?

> "V1 is strict — refuses anything not explicitly in the document. Good for compliance use cases. V2 is more charitable — if you ask 'is there anything for me here?', it interprets the question and answers from relevant context rather than refusing because your name isn't in the doc."

### Model choice — nemotron-3-super-120b-a12b

### `[ EXPLAIN TO AUDIENCE ]` — What is Mixture of Experts (MoE)?

> "Traditional LLMs activate all their parameters for every token they generate. A Mixture of Experts model splits its parameters into 'experts' — specialized sub-networks — and only activates a few of them per token. nemotron has 120 billion total parameters but only 12 billion active per inference. So you get quality close to a 120B model at the cost and speed of a 12B one. That's why it runs in about 30 seconds on the free tier despite being a 120B model."

---

## Live Demo Flow

### `[ DEMO ]`

From product_manual.txt (NovaSuite):
   What is the price of the Enterprise plan?
   How many members can join a project on the Standard plan?
   How much storage does the Free plan include?
   How long is a password reset link valid?
   What discount do you get for switching to annual billing?
   How many failed login attempts trigger an account lockout?

From company_policy.pdf:
   How many days of annual leave do full-time employees get?
   What is the notice period for a senior manager?
   How many sick leave days are allowed during probation?
   How many days in advance must annual leave be approved?
   How many days of paternity leave does the policy give?
   What is the expense approval threshold that requires a manager signature?

From annual_report.pdf:
   Which department is at risk of overspending?
   What is the total approved budget across all departments?
   How much has the Engineering department spent so far in Q3?

From quarterly_sales.xlsx:
   Which product missed its Q3 sales target?
   Who is the top sales performer by revenue?
   How many salespeople exceeded their quota this quarter?

Unanswerable — should trigger a refusal:
   When was Acme Corp founded?
   What is the CEO's name?

1. **Upload a document** — show the file chip appearing in the header with chunk count
   - Point out: "The number next to the filename is how many chunks it was split into"

2. **Ask a specific factual question** — e.g. "How many days of annual leave do employees get?"
   - Point out the answer, then scroll to citations
   - "See this similarity score of 0.87 — that means the retrieval step was confident it found the right chunk. And this is the exact text from the document the LLM used to answer."

3. **Open the settings panel** — walk through each control
   - Model — which LLM generates the answer
   - Prompt version — V1 strict vs V2 moderate
   - Top-K chunks — how many chunks to retrieve (more = more context, but slower and noisier)
   - Temperature — how creative vs deterministic the LLM is (0 = always same answer, 2 = very random)
   - Top-P — controls diversity of word choices
   - Max tokens — maximum length of the answer

4. **Ask an unanswerable question** — "When was the company founded?"
   - "The LLM says 'I could not find this in the provided documents' — that's the correct behaviour. It didn't make something up. That's the whole point of RAG."

5. **Upload a second file** — show multiple chips, ask a cross-document question

---

## Challenges Worth Mentioning

> "A few real production-like issues came up:"

- **Corporate SSL interception** — Accenture's proxy intercepts HTTPS, so any outbound API call fails cert validation. Solved with `verify=False` on the httpx client. In production you'd add the corporate cert bundle.
- **Model deprecations** — The NVIDIA free tier deprecated llama-3.1-8b mid-project with 502 errors. Had to identify and switch models. Shows why model config should always be an env variable, not hardcoded.
- **LangChain version conflicts** — Installing one package for the eval layer (P3) downgraded langchain-core and broke P2. Real dependency management problem — same thing happens in production microservices with shared venvs.

---

## What P3 Adds (teaser)

> "P2 tells you it works. P3 tells you how well it works — with numbers."

### `[ EXPLAIN TO AUDIENCE ]` — Why do you need evaluation?

> "When you build a RAG system, 'it looks good' is not a reliable quality signal. You need to measure:
>
> - Context precision — did the retrieval step fetch relevant chunks, or noisy ones?
> - Context recall — did it fetch all the relevant chunks, or miss some?
> - Faithfulness — did the LLM stay within the retrieved context, or hallucinate?
> - Answer relevancy — did it actually answer the question?
>
> P3 builds an automated harness that runs 20 hand-authored test questions against the system and scores it on all these dimensions. Below a threshold on any metric — it doesn't ship.
>
> The critical design choice: you never use the same model to judge its own outputs. A model rates its own answers higher — that's self-serving bias. We used gpt-oss-20b, a reasoning model from a completely different family, as the independent judge."

---

## One-line Summary (closing)

> "P2 is a production-pattern RAG system — persistent vector store, configurable retrieval, two prompt strategies, cited answers, and a clean UI. The architecture is the same pattern you'd build at scale, just with a free-tier NVIDIA API instead of enterprise infrastructure."

---

Tip: For a technical audience, spend more time on embeddings, chunking strategy, and MoE. For a business audience, focus on the problem it solves, the demo, and the hallucination prevention story.

---

## Q&A Prep — "Why a different model as judge? Why not the same one?"

This question will come up. Here is how to answer it confidently.

### The short answer

> "Using the same model to judge its own outputs is like marking your own exam. The model has a systematic preference for its own style of reasoning — so it scores itself higher than an independent evaluator would. You get inflated scores that don't reflect real quality. That's called self-serving bias."

### What actually happens if you use the same model

> "Say the generator model has a habit of being vague when it's uncertain — instead of saying 'I don't know', it gives a soft non-answer. If you use the same model as the judge, it will recognise that pattern as 'reasonable' and score it 4 out of 5. An independent judge from a different family would call it out as a non-answer and score it 2. The eval passes internally but fails in the real world. That's exactly the failure mode we're trying to prevent."

Concrete failure pattern to mention:

- Generator hallucinates in a confident tone
- Same-model judge sees confident tone → scores faithfulness high
- Independent judge reads the claim against the context → flags it as hallucination
- Result: same-model eval says PASS, independent eval says FAIL

### Why a reasoning model specifically (gpt-oss-20b)

> "A reasoning model doesn't just look at the surface of the answer — it works through a chain of thought before scoring. It reads the retrieved context, reads the answer, then reasons about whether every claim in the answer is actually supported. That's a much stronger faithfulness check than a standard model that scores by pattern-matching the tone."

### Pros of using a different model as judge

- **No self-serving bias** — scores reflect actual quality, not stylistic familiarity
- **Catches systematic errors** — if the generator always makes the same type of mistake, an independent judge from a different training distribution will catch it
- **Industry standard** — this is how GPT-4 is used to evaluate smaller models in most published research
- **Reasoning models add explainability** — gpt-oss-20b outputs its reasoning chain, so you can see *why* it gave a score, not just what score it gave

### Cons / trade-offs to be honest about

- **Extra cost** — you're making API calls to two different models per eval run (generator + judge). For 20 questions that's 40 calls minimum, plus RAGAS which adds more.
- **Judge model can also be wrong** — no judge is perfect. A different model introduces its own biases. The assumption is that two independent biases are less correlated than one model's bias with itself.
- **Latency** — a reasoning model like gpt-oss-20b takes longer per call than a standard model because it generates a chain-of-thought before answering. Eval runs are slow.
- **Not free at scale** — on the NVIDIA free tier this works. In production with thousands of documents you'd need to budget for judge model API costs separately.

### Cost-effectiveness framing

> "The way to think about it: eval runs don't happen on every user query — they happen before you ship a change. You run it once, it costs a few extra API calls, and it tells you whether your system is ready. That's a small price compared to shipping a broken RAG system and losing user trust. The judge model cost is a quality gate investment, not a per-request overhead."
