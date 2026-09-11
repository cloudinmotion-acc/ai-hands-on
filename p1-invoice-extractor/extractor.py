from dotenv import load_dotenv
import os
import re
import time
import json
from openai import OpenAI
from schemas import Invoice

load_dotenv()

client = OpenAI(
        api_key=os.getenv("NVIDIA_API_KEY"),    
        base_url=os.getenv("NVIDIA_BASE_URL")
    )
MODEL: str = os.getenv("NVIDIA_MODEL") or ""

def _parse_json(text: str) -> dict:
    # reasoning models think out loud before the JSON — strip everything before the first {
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM response:\n{text}")
    return json.loads(match.group())


def extract(images: list[str]) -> Invoice:
    print(f"[1/4] Sending {len(images)} page(s) to LLM for extraction...")
    raw = _call_llm(images, _extract_prompt())
    print(f"[2/4] Raw extraction done. Self-verifying...")
    print(f"      → {raw[:120]}...")   # preview first 120 chars
    verified = _call_llm(images, _verify_prompt(raw))
    print(f"[3/4] Verification done. Parsing JSON...")
    data = _parse_json(verified)
    print(f"[4/4] Validating schema...")
    return Invoice.model_validate(data)

def _call_llm(images: list[str], prompt: str, retries: int = 3) -> str:
    content = [{"type": "text", "text": prompt}]
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img}"}
        })

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=2048,
                temperature=0.2,
                extra_body={"reasoning_budget": 512},
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt        # 1s → 2s → 4s
            print(f"Attempt {attempt + 1} failed ({e}). Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("All retries exhausted")

def _extract_prompt() -> str:
     return """You are an invoice data extractor.

        Extract these fields from the invoice image and return ONLY valid JSON, no explanation:

        {
            "invoice_no": "the invoice/bill/estimate number as a string",
            "vendor_name": "business name only, no address",
            "date": "date exactly as written on the invoice",
            "total": "final amount as a number (Grand Total / Net Payable / Total)",
            "subtotal": "amount before tax as a number, or null if not shown",
            "tax": "total tax amount as a number (GST/CGST+SGST combined), or null if not shown",
            "payment_method": "how it was paid (Cash/UPI/Card etc), or null if not shown",
            "gstin": "vendor GSTIN number if present, or null"
        }

        Rules:
        - Return null for any field not present on the invoice. Never guess or calculate.
        - Numbers must be plain numbers, no currency symbols.
        - Return ONLY the JSON object, nothing else.
    """

def _verify_prompt(extracted_json: str) -> str:
    return f"""
        You are a verification agent. You extracted this JSON from an invoice:

        {extracted_json}

        Look at the invoice image again carefully. Check every field.
        If anything is wrong or missing, fix it.
        Return ONLY the corrected JSON object, no explanation. Same format.
    """