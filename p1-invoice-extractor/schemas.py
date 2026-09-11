from decimal import Decimal
from pydantic import BaseModel, field_validator


class Invoice(BaseModel):
    invoice_no:     str
    vendor_name:    str
    date:           str           # normalized to YYYY-MM-DD
    total:          Decimal
    subtotal:       Decimal | None = None
    tax:            Decimal | None = None
    payment_method: str | None = None
    gstin:          str | None = None

    @field_validator("date")
    @classmethod
    def normalize_date(cls, v: str) -> str:
        from dateutil import parser as dateparser
        try:
            return dateparser.parse(v, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            return v  # return as-is if unparseable, extractor's problem not validator's
