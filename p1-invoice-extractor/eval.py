"""
Prompt version evaluator for P1 Invoice Extractor.
Runs each prompt version against all invoices and scores field-by-field accuracy.
"""

from dotenv import load_dotenv
import os, json, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from openai import OpenAI
from reader import file_to_images

load_dotenv()
client = OpenAI(api_key=os.getenv("NVIDIA_API_KEY"), base_url=os.getenv("NVIDIA_BASE_URL"))
MODEL: str = os.getenv("NVIDIA_MODEL") or ""

INVOICE_PATH = Path(__file__).parent / "invoices" / "invoices-poc1.pdf"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"
PROMPTS_DIR = Path(__file__).parent / "prompts"
NUMERIC_FIELDS = {"total", "subtotal", "tax"}
STRING_FIELDS  = {"invoice_no", "vendor_name", "date", "payment_method", "gstin"}

# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    start = text.find('{')
    if start == -1:
        raise ValueError(f"No JSON in response:\n{text[:300]}")
    obj, _ = json.JSONDecoder().raw_decode(text, start)
    return obj


def _call_llm(images: list[str], prompt: str, retries: int = 3) -> str:
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=1024,
                temperature=0.0,
                extra_body={"reasoning_budget": 256},
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt
            print(f"      [retry {attempt+1}] {e} — waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("All retries exhausted")


def _null(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() == "null")



def _field_matches(field: str, predicted, expected) -> bool:
    """Compare predicted vs expected for a single field."""
    # Both null → match
    if _null(expected) and _null(predicted):
        return True
    # One null, one not → mismatch
    if _null(expected) != _null(predicted):
        return False

    if field in NUMERIC_FIELDS:
        try:
            p = Decimal(str(predicted))
            e = Decimal(str(expected))
            return abs(p - e) < Decimal("0.05")
        except InvalidOperation:
            return False

    if field == "date":
        import re as _re
        from datetime import datetime
        _DATE_FMTS = [
            "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y",
            "%d-%m-%Y", "%d-%m-%y",
            "%d-%b-%Y", "%d-%b-%y",
            "%d %b %Y", "%d %b %y",
        ]
        def _norm(s: str) -> str:
            # strip trailing time component e.g. "18-Jan-26 2:10:39 PM"
            s = _re.split(r'\s+\d{1,2}:', s.strip())[0].strip()
            for fmt in _DATE_FMTS:
                try:
                    return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return s
        return _norm(str(predicted)) == _norm(str(expected))

    if field == "payment_method":
        p = str(predicted).strip().lower()
        e = str(expected).strip().lower()
        return e in p or p in e

    # String comparison — case-insensitive, stripped
    return str(predicted).strip().lower() == str(expected).strip().lower()


def _score_result(predicted: dict, expected: dict) -> dict[str, bool]:
    fields = list(STRING_FIELDS | NUMERIC_FIELDS)
    return {f: _field_matches(f, predicted.get(f), expected.get(f)) for f in fields}


# ── main eval loop ────────────────────────────────────────────────────────────

def run_eval():
    ground_truths = json.loads(GROUND_TRUTH_PATH.read_text())
    # Sort ground truths by source_page so they match page order
    ground_truths_by_page = {gt["source_page"]: gt for gt in ground_truths}

    # Each page in the PDF is one invoice — load as individual page images
    all_images = file_to_images(str(INVOICE_PATH))
    print(f"Loaded {len(all_images)} pages from PDF\n")

    prompt_files = sorted(PROMPTS_DIR.glob("*.txt"))
    all_fields = sorted(STRING_FIELDS | NUMERIC_FIELDS)

    # results[version_name][page_num] = {field: bool}
    all_results: dict[str, dict[int, dict[str, bool]]] = {}

    for prompt_file in prompt_files:
        version = prompt_file.stem
        prompt_text = prompt_file.read_text()
        print(f"=== Running {version} ===")
        all_results[version] = {}

        for page_num, gt in ground_truths_by_page.items():
            page_idx = page_num - 1  # 0-indexed
            print(f"  Page {page_num} ({gt['vendor_name']})...", end=" ", flush=True)
            try:
                raw = _call_llm([all_images[page_idx]], prompt_text)
                predicted = _parse_json(raw)
                scores = _score_result(predicted, gt)
                correct = sum(scores.values())
                print(f"{correct}/{len(scores)} fields correct")
                for f, ok in scores.items():
                    if not ok:
                        print(f"    MISMATCH {f}: got={predicted.get(f)!r}  expected={gt.get(f)!r}")
                all_results[version][page_num] = scores
            except Exception as e:
                print(f"ERROR: {e}")
                all_results[version][page_num] = {f: False for f in all_fields}

        time.sleep(2)  # brief pause between versions to avoid rate limits
        print()

    # ── print summary table ───────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("ACCURACY SUMMARY (per version, across all invoices)")
    print("=" * 80)

    vendors = [ground_truths_by_page[p]["vendor_name"].split()[0] for p in sorted(ground_truths_by_page)]
    header_pages = "  ".join(f"P{p}" for p in sorted(ground_truths_by_page))
    print(f"{'Version':<22} {'Avg':>5}   {header_pages}")
    print("-" * 80)

    for version in [f.stem for f in prompt_files]:
        if version not in all_results:
            continue
        page_scores = []
        per_page = []
        for page_num in sorted(ground_truths_by_page):
            field_results = all_results[version].get(page_num, {})
            score = sum(field_results.values()) / len(all_fields) * 100 if field_results else 0.0
            page_scores.append(score)
            per_page.append(f"{score:5.0f}%")
        avg = sum(page_scores) / len(page_scores) if page_scores else 0.0
        print(f"{version:<22} {avg:5.1f}%   {'  '.join(per_page)}")

    print()
    print("PER-FIELD BREAKDOWN (% correct across all invoices per version)")
    print("-" * 80)
    print(f"{'Field':<18}", end="")
    for f in [pf.stem for pf in prompt_files]:
        print(f"  {f[:8]:>8}", end="")
    print()
    print("-" * 80)

    for field in all_fields:
        print(f"{field:<18}", end="")
        for version in [pf.stem for pf in prompt_files]:
            field_correct = sum(
                all_results[version].get(p, {}).get(field, False)
                for p in ground_truths_by_page
            )
            pct = field_correct / len(ground_truths_by_page) * 100
            print(f"  {pct:>7.0f}%", end="")
        print()

    print()
    print("Legend: P1=Raju Gari Biryani, P2=Maangalya Mall, P3=Sri Shyam, P4=Ratnadeep")


if __name__ == "__main__":
    run_eval()
