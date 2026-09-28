# P1 — Invoice AI

Structured data extraction from invoice images and PDFs using an LLM, with a self-verification pass that flags low-confidence fields.

## What it does

Upload a PDF or image invoice → LLM extracts structured JSON (vendor, line items, totals, dates) → a second LLM pass verifies each field → results shown in the browser with confidence scores.

## Stack

- Streamlit (UI)
- NVIDIA NIM (`nemotron-3-super`)
- No database

## Setup

```bash
cd p1-invoice-extractor
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY
```

**.env**
```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=nvidia/nemotron-3-super
```

## Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` — drag and drop an invoice to get started.

## Project structure

```
p1-invoice-extractor/
  app.py          ← Streamlit UI + file upload
  extractor.py    ← LLM extraction + verification logic
  requirements.txt
  .env.example
```
