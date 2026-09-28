# P1 — Invoice AI · Demo Notes

---

## The Problem

Finance teams process hundreds of invoices a week — manually keying vendor names, line items, totals, and dates into systems. It's slow, expensive, and error-prone. A 1% error rate on 500 invoices a week is 5 wrong entries that someone has to chase down later.

The obvious fix is to use an LLM to read the invoice and extract the fields. But the obvious fix has an obvious problem: how do you know the LLM got it right? It could hallucinate a total, misread a line item, or invent a date. A wrong entry that gets automated is worse than a slow manual one.

---

## The Solution

Two LLM passes, not one.

**Pass 1 — Extract:** The LLM reads the invoice and returns structured JSON (vendor, invoice number, date, line items, subtotal, tax, total).

**Pass 2 — Verify:** A second LLM call receives the extracted JSON and the original invoice together and checks every field. It returns a confidence score per field and flags anything it isn't certain about.

The user sees the extracted data with a confidence indicator on each field. Low-confidence fields are highlighted so a human knows exactly what to check — instead of having to re-read the whole invoice.

---

## What Makes This Different

**vs. standard tutorials:**
Most extraction demos do one LLM call and display the output. There's no quality check. If the LLM says the total is ₹12,400 when it's really ₹14,200, the demo still looks like it worked. This adds a self-verification pass — a reflection pattern — that makes failures visible.

**vs. off-the-shelf OCR tools:**
Tools like AWS Textract or Google Document AI do optical character recognition but require you to define field templates per invoice layout. This approach is layout-agnostic — the LLM understands invoice structure semantically, so it works on any format without configuration.

**vs. colleagues / other portfolio projects:**
Most people show extraction. Few show verification. The verification pass demonstrates understanding of LLM failure modes — hallucination, overconfidence — and a concrete mitigation.

---

## Demo Tour

### Before you start
- [ ] Backend running: `streamlit run app.py` from `p1-invoice-extractor/`
- [ ] Have a PDF or image invoice ready to upload (any real invoice works)

---

### Step 1 — Open the app
**Open:** `http://localhost:8501`

**Say:**
> "This is the Invoice AI app. The idea is simple — drop in any invoice, get back structured data, and know which fields to trust. There's no template setup, no layout configuration — it works on any invoice format."

---

### Step 2 — Upload an invoice
**Do:** Click the upload area, select your invoice file.

**Say:**
> "I'm uploading a real invoice here. The system accepts PDF or image formats. It's going to make two LLM calls — first to extract the fields, then to verify its own output."

---

### Step 3 — Show the extracted JSON
**Do:** Wait for the extraction to complete, point to the JSON output.

**Say:**
> "Here's what came back from the first pass — vendor name, invoice number, date, every line item with quantity and unit price, subtotal, tax, and total. All structured. This took about 3 seconds."

---

### Step 4 — Show confidence scores
**Do:** Point to the confidence indicators per field.

**Say:**
> "This is the part most demos skip. A second LLM call takes this extracted JSON, compares it back to the original invoice, and scores each field's confidence. Green means high confidence — the LLM is sure. Amber means check this manually. If the total doesn't add up from the line items, that field gets flagged automatically."

> "For a finance team this means: automation handles the bulk, humans only touch the flagged fields. You're not trusting a black box — you're getting a prioritised review queue."

---

### Step 5 — (If time) Try a tricky invoice
**Do:** Upload a handwritten or multi-currency invoice if you have one.

**Say:**
> "Let me show what happens with a more difficult input. Notice the confidence scores drop on the ambiguous fields — the system tells you where it's uncertain instead of guessing silently."

---

## Code Walkthrough

### `app.py` — Streamlit UI and file handling
**What it does:** Entry point. Handles file upload, calls the extractor, renders the JSON output and confidence scores in the browser.

**Key function: file upload handler (top-level Streamlit code)**
```python
uploaded_file = st.file_uploader("Upload an invoice", type=["pdf", "png", "jpg"])
if uploaded_file:
    result = extractor.extract_and_verify(uploaded_file)
    st.json(result["extracted"])
    # renders confidence per field
```
Plain English: Streamlit re-runs the whole script every time the user interacts. When a file is uploaded, it immediately calls the extractor and displays whatever comes back. No backend server needed — Streamlit is the server.

---

### `extractor.py` — Two-pass LLM logic
**What it does:** Makes two LLM calls — extract then verify — and returns a combined result.

**Key function: `extract_and_verify(file)`**

Pass 1 — extraction prompt tells the LLM: "Read this invoice, return JSON with these exact keys." Temperature = 0 (deterministic — you want the same answer every time for the same invoice).

Pass 2 — verification prompt tells the LLM: "Here is the original invoice. Here is what was extracted. For each field, score your confidence 0–1 and flag anything that looks wrong." The LLM checks its own previous output.

**Why two passes instead of one?** Asking the LLM to extract AND verify in one prompt creates a conflict — it's harder for the model to be self-critical when it just generated the answer. Separate prompts separate the roles: one LLM as extractor, one as auditor.

---

## New Concepts to Stress

### LLM Self-Verification (Reflection Pattern)
One of the most practically useful patterns in LLM engineering. Instead of trusting one output, you use a second LLM call to critique the first. The key insight is that LLMs are better at spotting errors in text than at avoiding them during generation — the same model that makes a mistake can often catch it when shown the mistake separately.

Used heavily in production: OpenAI's o1 uses internal self-critique, RAGAS (P3) uses it for faithfulness scoring, and this project uses it explicitly.

### Temperature = 0 for Structured Output
When you need consistent, structured JSON from an LLM, temperature=0 removes sampling randomness. You get the same answer for the same input every time. This matters for extraction tasks — creative variance is the enemy. Save higher temperatures for generation tasks where variety is useful.

---

## Conclusion

P1 demonstrates the core discipline of LLM engineering: **don't trust a single model call, verify it**. The extraction is not the hard part — any LLM can read an invoice. The hard part is knowing when the output is wrong. The self-verification pass is the production-grade addition that transforms a demo into something deployable.

**Key takeaway for the room:** Every automated AI output in a real system should have a quality gate. P1 shows the simplest version of that gate — the model checking its own work.
