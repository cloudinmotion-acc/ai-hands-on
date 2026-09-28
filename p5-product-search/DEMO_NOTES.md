# P5 — Hybrid Product Search · Demo Notes

---

## The Problem

Product search is deceptively hard. A user query like "comfortable yoga pants for women in stock under ₹800" has three different kinds of intent packed into one sentence:

- **Structured constraints:** gender=women, in_stock=true, max_price=800 — these need exact database matching, not interpretation
- **Semantic meaning:** "comfortable yoga pants" — no product in the catalogue is literally named "yoga pants", but there are "wide-leg palazzo pants" and "elasticated waist palazzo" that match the concept
- **Keyword:** specific terms that should find exact matches before semantic ones

No single retriever handles all three. SQL can't understand "yoga pants". BM25 finds every product with "pants" in it without knowing you want women's. A vector search ranks by semantic closeness but can't enforce "in stock = true".

---

## The Solution

Three retrievers running in parallel, merged by RRF.

1. **SQL filter** — takes the structured constraints (gender, price, stock status) and runs a parametric WHERE clause against PostgreSQL. Exact, fast, zero false positives on structured attributes.

2. **BM25 (keyword)** — takes the semantic query string and scores all 65 products by keyword overlap with name + description. Built in-memory at startup, zero latency.

3. **pgvector (semantic)** — embeds the semantic query into a 2048-dimensional vector, runs cosine similarity against pre-embedded product descriptions. Understands synonyms and concepts.

4. **RRF merge** — Reciprocal Rank Fusion: every product gets `1 / (60 + rank)` from each retriever list it appears in. Products that rank well across multiple retrievers score highest. No score calibration needed.

5. **Post-RRF hard filter** — gender and in_stock are enforced as hard gates after the merge. BM25 and vector don't understand gender — this filter prevents the wrong-gender products from leaking through.

6. **MCP tool + LangGraph agent** — the entire pipeline is wrapped as a single MCP tool. The LangGraph agent calls it once, gets back structured results, and writes a natural language answer.

---

## What Makes This Different

**vs. Elasticsearch:**
Elasticsearch can do BM25 + vector hybrid search, but setting it up requires managing an Elasticsearch cluster, defining index mappings, writing BEL (Elasticsearch Query DSL), and it doesn't include an LLM layer. P5 is a self-contained system: one Docker container for pgvector, one Python process for the BM25 index, all wired together in Python you can read and modify.

**vs. Pinecone / managed vector databases:**
Managed services give you vector search but not SQL filtering or BM25. You'd need to add those separately. P5 shows the full three-leg approach in a single coherent system.

**vs. basic RAG tutorials:**
Tutorials do single-retriever (vector only). P5 shows why that's insufficient and builds the full hybrid pipeline. The eval (Precision@5) makes the improvement measurable.

**vs. standard LangChain retrievers:**
LangChain has `EnsembleRetriever` for combining BM25 + vector. It doesn't include SQL as a leg, doesn't do adaptive pool sizing, and doesn't have post-merge demographic filtering. P5 builds the merge logic from scratch with `merger.py`, so every decision is visible and tunable.

---

## Demo Tour

### Before you start
- [ ] PostgreSQL pgvector container running, database `p5_rag` with products ingested
- [ ] Backend: `uvicorn main:app --port 8000` from `p5-product-search/backend/`
- [ ] Frontend: `npm run dev` from `p5-product-search/frontend/` (starts on port 3001)

---

### Step 1 — Open the app
**Open:** `http://localhost:3001`

**Say:**
> "This is the Hybrid Product Search. It looks like a shopping chatbot but the retrieval engine behind it is doing three things simultaneously — exact SQL filtering, keyword search, and semantic vector search. Let me show you why each one matters."

---

### Step 2 — Show a structured query (SQL wins)
**Do:** Type: `"affordable kids clothing under ₹300 in stock"`

**Say:**
> "This is a structured query — price ceiling, stock status. Watch what gets decomposed first."

**Point to the decomposed filters panel:**
> "The LLM decomposer split the query into a semantic part ('affordable kids clothing') and structured filters: max_price=300, in_stock=true. The SQL retriever used those filters to find exactly the products that match — the vector and BM25 legs also ran but for this query, the SQL leg is doing the most work. All results are priced under ₹300 and in stock."

---

### Step 3 — Show a semantic query (vector wins)
**Do:** Type: `"comfortable yoga pants for women"`

**Say:**
> "Now a semantic query. There are no 'yoga pants' in the catalogue. Watch what comes back."

**Point to results:**
> "It found women's wide-leg palazzo pants and elasticated waist trousers — products that match the concept of 'yoga pants' without containing those exact words. That's the vector retriever working. BM25 would have returned nothing for 'yoga' because the word doesn't appear anywhere in the product data. Vector search understands meaning across vocabulary."

---

### Step 4 — Show the mismatch badges
**Do:** Type: `"silk blouse for women under ₹800"`

**Say:**
> "This is a query where the catalogue genuinely doesn't have an exact match — the only silk blouse costs ₹2100. Watch what happens."

**Point to product cards with amber badges:**
> "The system returns near-matches — the closest women's blouses in the right price range. But it's honest about the gap: the amber badges with the warning icon tell you exactly which attributes don't match. That fabric badge says 'cotton' with a warning because you searched for silk. The system is being transparent about what it found versus what you asked for."

> "Most search systems either show wrong results silently or show nothing. This shows you near-matches AND tells you why they're near-matches, not exact matches."

---

### Step 5 — Show the injection fix (gender filter)
**Do:** Type: `"ethnic kurta for girls"`

**Say:**
> "This query was broken before a fix I'll show in the code. There are lots of men's and women's kurtas in the catalogue. BM25 finds them all because they contain the word 'kurta'. Without a gender filter, men's kurtas dominate the results. The correct item — Yellow Anarkali Suit — doesn't even have 'kurta' in its description."

**Point to results:**
> "After the post-RRF hard filter, all non-girls items are removed. The correct result surfaces. This is why gender is a hard gate, not a soft preference."

---

### Step 6 — Run the eval (if time)
**Do:** Open a terminal and run `python eval/run_eval.py`

**Say:**
> "The eval runs 15 queries in all three modes — BM25 only, vector only, hybrid — and measures Precision@5. BM25 averages 0.28, vector averages 0.32, hybrid averages 0.32. The numbers are similar in average, but hybrid enforces structured constraints that neither BM25 nor vector can do alone. Q11 — the kurta query — goes from 0.00 to 0.20 with the hard filter."

---

## Code Walkthrough

### `search/decomposer.py` — LLM query splitter
**What it does:** Makes one LLM call to split the raw user query into `semantic_query` (for BM25 and vector) and `filters` (for SQL).

**Key function: `decompose(query)`**
The system prompt explicitly bans the `category` key — learned from eval failure where the LLM extracted `category="women"` but the DB column stores item types ("pants", "dress"), not demographics. `WHERE category='women'` returned 0 rows. Removing it from the schema fixed Q4 from 0.40 to 0.60.

Temperature = 0: the decomposer is a parser, not a generator. Same input must produce same output every time.

Fallback: if the JSON parse fails for any reason, returns `{semantic_query: original_query, filters: {}}` — the pipeline continues with degraded quality rather than throwing an error.

---

### `search/merger.py` — RRF fusion
**What it does:** Takes three ranked lists (SQL, BM25, vector) and produces one merged ranked list using Reciprocal Rank Fusion.

**Key function: `merge(sql_results, bm25_results, vector_results, top_k)`**
```python
_K = 60  # smoothing constant from the original RRF paper

for rank, product in enumerate(ranked_list, start=1):
    rrf_scores[pid] += 1.0 / (_K + rank)
```
Plain English: for each product, add up `1/(60 + rank)` from every list it appears in. Products appearing in all three lists score much higher than products appearing in only one. The 60 smoothing constant dampens the difference between rank 1 and rank 5 — you're not winner-takes-all.

Example with numbers: product ranked 3rd in SQL, 1st in BM25, 5th in vector:
`1/63 + 1/61 + 1/65 = 0.0477` vs a product only in BM25 at rank 1: `1/61 = 0.0164`. Multi-retriever validation scores 2.9× higher.

---

### `mcp_server.py` — pipeline orchestrator + MCP tool
**What it does:** Wraps the entire 7-step pipeline as a single `@mcp.tool()`. The LangGraph agent calls `search_products(query)` and gets back JSON. It doesn't need to know about SQL, BM25, vector, or RRF.

**Key function: `_hard_filter(products, filters)`**
```python
if gender_want:
    pg = p.get("gender", "").lower()
    if pg != gender_want and pg != "unisex":
        continue  # drop wrong gender
```
Two key decisions here: gender and in_stock are hard gates (showing wrong gender = wrong result); colour and fabric are soft (showing cotton when silk was asked = near-match, shown with amber badge). Unisex products pass any gender filter — discovered this after the hard filter incorrectly dropped ID 31 (Oversized Cozy Hoodie) for "fleece hoodie for men" queries.

**Key pattern: adaptive pool sizing**
```python
pool_k = top_k * 4 if filters else top_k * 2
```
When filters are present, we need a larger pool for the hard filter to have items to work with after it removes wrong-gender results. For open queries (no filters), a smaller pool avoids diluting the RRF merge. This fixed a regression where flat 4× pool hurt Q9 (floral print summer dress) by adding too much noise.

---

### `search/sql_filter.py` — structured SQL retriever
**What it does:** Builds a parametric SQL WHERE clause from the filters dict. Uses `psycopg2.extras.RealDictCursor` to return rows as dicts. All conditions are AND-ed.

Parametric queries only — no string interpolation. `WHERE LOWER(gender) = LOWER(%s)` with params, never `f"WHERE gender = '{gender}'"`. This prevents SQL injection at the data layer.

---

### `search/bm25_retriever.py` — keyword index
**What it does:** At module import time, loads all 65 products and builds a `BM25Okapi` index on name + description. Tokenises with `re.findall(r"[a-z0-9]+", text.lower())`.

Zero-latency after startup because the index is in memory. Zero-score results are excluded — if a product has no keyword overlap with the query, it shouldn't be in the BM25 leg at all. Including zero-score items would dilute the RRF merge.

---

### `frontend/app/page.tsx` — mismatch highlighting
**What it does:** The UI component that receives decomposed filters from the `tool_result` SSE event and computes attribute mismatches against each product card client-side.

**Key function: `computeMismatches(product, filters)`**
```typescript
if (filters.fabric && s(product.fabric) !== s(filters.fabric))
    mismatches.add("fabric");
if (filters.gender) {
    const pg = s(product.gender);
    if (pg !== s(filters.gender) && pg !== "unisex")
        mismatches.add("gender");
}
```
Pure frontend — no backend change needed. The `tool_result` event already contains both the filters and the products. The UI diffs them and renders amber badges for mismatched attributes. The tooltip says "You searched for: {filter_value}" so users know exactly what they asked for vs what they got.

---

### `eval/run_eval.py` — Precision@5 evaluation
**What it does:** Runs each of 15 queries through all three retrieval modes (BM25-only, vector-only, hybrid), computes Precision@5 per query, reports averages and per-query breakdown.

**Key function: `precision_at_k(results, expected_ids, k=5)`**
```python
top_ids = [r["id"] for r in results[:k]]
hits = sum(1 for pid in top_ids if pid in expected_ids)
return hits / min(k, len(top_ids))
```
Denominator is `min(k, len(top_ids))` — if the retriever returns fewer than 5 results, the denominator is the actual result count, not 5. This prevents penalising the system for catalogue gaps — a query with only 1 expected item can score 1.0 by finding that item, not 0.20.

---

## New Concepts to Stress

### Reciprocal Rank Fusion (RRF)
Published by Cormack, Clarke, and Buettcher in 2009. The key insight: when combining ranked lists from heterogeneous sources, use rank position rather than raw scores. Raw scores can't be compared across systems — BM25 scores and cosine similarities live in completely different scales. Ranks can. The formula `1/(k + rank)` is simple enough to implement in 10 lines and robust enough that it's used in production systems at scale (Microsoft, Elasticsearch, Weaviate all support it).

### MCP (Model Context Protocol)
Anthropic's open protocol for exposing capabilities to LLMs as tools. A FastMCP `@mcp.tool()` decorator turns any Python function into a tool that any MCP-compatible client can call. The advantage: the tool contract (name, description, parameters, return type) is standardised. An agent that knows how to call MCP tools can call `search_products` whether the implementation is SQL, BM25, vector, or any combination. Implementation can change without touching agent code.

### Precision@k
The standard evaluation metric for ranked retrieval systems. "Of the top k results returned, what fraction were correct?" For k=5, a perfect score of 1.0 means all 5 results are expected matches. 0.40 means 2 of 5. When a query has only 1 expected item, the best possible Precision@5 is 0.20 (found the 1 item in 5 results). This context matters when reading eval numbers — low absolute scores don't always mean poor performance; they often reflect catalogue sparsity.

---

## Conclusion

P5 demonstrates that real-world search is a system design problem, not a model selection problem. The right approach is to understand what each retriever is good at, run them in parallel, merge intelligently, and enforce business rules as post-merge gates. The MCP wrapper means this entire pipeline is accessible to any agent as a single tool call — the complexity is hidden behind a clean interface.

**Key takeaway for the room:** Hybrid search outperforms single-retriever approaches not because any one retriever is better, but because they cover different failure modes. The eval proves it — and the eval is what separates engineering from guessing.
