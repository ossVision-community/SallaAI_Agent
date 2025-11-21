# app/agent/normalizers.py
from __future__ import annotations

from typing import Dict, Any, Optional


def spec_normalizer(name: str, retailer: str, condition: str) -> Dict[str, Any]:
    """Normalize model, storage, and condition from raw product text."""
    txt = f"{name} {retailer} {condition}".lower()

    if ("pro max" in txt) or ("promax" in txt) or (" ماكس" in txt):
        model = "iPhone 15 Pro Max"
    elif ("15 pro" in txt) or (" 15 برو" in txt):
        model = "iPhone 15 Pro"
    else:
        model = None

    storage = "256GB" if ("256" in txt or "٢٥٦" in txt) else None

    cond_raw = (condition or "").strip()
    cl = cond_raw.lower()
    if cl in {"new", "brand new", "جديد"}:
        cond = "New"
    elif "refurb" in cl or cl in {"مجدَّد", "منتَجات مجدَّدة"}:
        cond = "Refurbished"
    elif cl.startswith("used"):
        cond = "Used"
    else:
        cond = cond_raw or "Unknown"

    return {"model": model, "storage": storage, "condition": cond}


def price_normalizer(price: float, currency: Optional[str]) -> Dict[str, Any]:
    """Normalize a price to SAR. If currency unknown, assume SAR."""
    if not currency or currency.upper() == "SAR":
        return {"price_sar": float(price), "currency": "SAR"}

    rates = {"USD": 3.75, "EUR": 4.1}
    factor = rates.get(currency.upper(), 1.0)
    return {"price_sar": float(price) * factor, "currency": currency.upper()}
