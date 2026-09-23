# P1 Invoice Extractor — Demo Speaker Notes

---

## OPENING (30 sec)

**What to say:**
"The problem is simple — businesses receive invoices in all formats, PDFs, scanned images, thermal receipts. Someone has to manually key in 8 fields per invoice. We're replacing that with an AI pipeline that reads the document and returns clean structured JSON in seconds."

---

## SHOW THE APP (1–2 min)

**Action:** Open browser → `http://localhost:8501` → run `streamlit run app.py` if not already up.

**What to say:**
"This is the interface. It takes a PDF or image — doesn't matter the format. Let me upload one of our test invoices."

**Action:** Upload `invoices-poc1.pdf` or any single invoice image.

**What to say:**
"Watch the steps — it sends the image directly to a vision LLM as base64. No OCR, no preprocessing. The model reads it like a human would."

**Action:** Wait for extraction to complete, point at the result table.

"Eight fields, clean JSON — vendor, invoice number, date normalized to ISO format, total, tax, payment method, GSTIN. Fields that aren't on the invoice come back as null, never a guess."

**Action:** Click Download JSON.

"And it's downloadable, ready to feed into any downstream system — ERP, accounting, audit trail."

---

## UNDER THE HOOD (1–2 min)

**What to say:**
"Three files, three responsibilities."

Point to the files in your editor or draw on whiteboard:

```
reader.py   → PDF/image → base64 images
extractor.py → LLM call with retry logic → raw JSON
schemas.py  → Pydantic validation → typed, clean Invoice object
```

"The schema is the contract. Everything else is plumbing. If the LLM returns a field in the wrong type, Pydantic catches it before it ever reaches the user."

**Key points to hit:**
- Vision model — no OCR step, handles handwritten/printed/thermal receipts
- Exponential backoff — production-grade, handles rate limits automatically
- Pydantic validator normalizes dates — `10/01/26`, `18-Jan-2026`, all become `2026-01-18`

---

## PROMPT VERSIONING (1 min)

**What to say:**
"Prompt engineering isn't guessing. We versioned it like code."

Point at the `prompts/` folder — show 5 files.

| Version | What changed |
|---|---|
| v1 | Zero-shot — just list the fields |
| v2 | Add role — "senior financial analyst at Big 4" |
| v3 | Few-shot — show one example extraction |
| v4 | Chain of thought — step-by-step reasoning |
| v5 | Strict field definitions with type rules |

"Each version is a hypothesis. We tested all of them against the same invoices with the same ground truth."

---

## EVAL RESULTS (1 min)

**Show terminal output from `python eval.py`:**

```
v1_zero_shot   84.4%
v2_role        81.2%
v3_few_shot    81.2%
v4_cot         87.5%   ← winner
v5_strict      68.8%
```

**What to say:**
"v4 — chain of thought — wins at 87.5%. The model reasons step by step before extracting, which catches edge cases like 'Estimate No' vs 'Invoice No', or a subtotal hidden in a multi-section receipt."

"The fields we don't get right 100% are GSTIN — those are 15-character alphanumeric codes the model sometimes misreads by one character. That's a visual OCR challenge, not a prompt problem."

---

## CLOSE (30 sec)

**What to say:**
"This is P1 — a linear extraction pipeline. Production-ready: retry logic, Pydantic validation, prompt versioning with a measurable accuracy score. Next phase adds RAG — pulling context from a document store — and eventually an agent that can reason across multiple invoices and flag anomalies."

"Questions?"

---

## IF ASKED ABOUT TECH STACK

- **Model:** NVIDIA-hosted vision + reasoning LLM via OpenAI-compatible API
- **Framework:** No LangChain for P1 — direct API, simpler to debug and explain
- **Validation:** Pydantic v2 — same library used in FastAPI, production standard
- **UI:** Streamlit — thin wrapper, zero business logic in the UI layer

## IF ASKED "WHY NOT JUST USE OCR?"

"OCR gives you text. We still need to parse structure from that text — which number is the total vs subtotal vs tax. The vision LLM does both in one step and handles noisy, scanned, or handwritten documents without preprocessing."

## IF ASKED ABOUT ACCURACY

"87.5% on 4 diverse real invoices with a single prompt. The misses are one-character GSTIN OCR errors — a post-processing GSTIN checksum validator would catch those. That's the next hardening step."
