# app/agent/tools.py
from __future__ import annotations

import re
from typing import List, Dict, Any, Optional

import requests

from app.core.config import SEARCHAPI_KEY
from app.core.constants import TRUSTED_KSA  # imported for completeness (if needed)


def normalize_retailer(name: Optional[str]) -> str:
    """Normalize retailer names and map variants to canonical trusted names."""
    if not name:
        return ""
    txt = (name or "").strip().lower()
    mapping = {
        "jarir bookstore": "Jarir",
        "jarir": "Jarir",
        "جرير": "Jarir",
        "extra": "eXtra Stores",
        "إكسترا": "eXtra Stores",
        "اكسترا": "eXtra Stores",
        "noon": "Noon.com",
        "نون": "Noon.com",
        "amazon.sa": "Amazon.sa",
        "amazon": "Amazon.sa",
        "أمازون": "Amazon.sa",
        "apple store": "Apple Store",
        "apple": "Apple Store",
        "أبل": "Apple Store",
        "aleph ألف": "Aleph ألف",
        "aleph": "Aleph ألف",
        "ألف": "Aleph ألف",
        "carrefour ksa": "Carrefour KSA",
        "كارفور": "Carrefour KSA",
    }
    for key, canon in mapping.items():
        if key in txt:
            return canon
    return (name or "").strip()


def shopping_search(
    query: str,
    gl: str = "sa",
    hl: str = "ar",
    google_domain: str = "google.com.sa",
    location: str = "Riyadh, Saudi Arabia",
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Search via SearchAPI.io Google Shopping and return normalized offers."""
    if not SEARCHAPI_KEY:
        raise RuntimeError("SEARCHAPI_KEY missing (set env var or .env).")

    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": gl,
        "hl": hl,
        "google_domain": google_domain,
        "location": location,
        "api_key": SEARCHAPI_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    out: List[Dict[str, Any]] = []
    for it in (data.get("shopping_results") or [])[:limit]:
        name = it.get("title")
        price = it.get("extracted_price")
        link = it.get("product_link")
        seller = it.get("seller")
        cond = it.get("condition")
        thumb = it.get("thumbnail")

        if not name or price is None or not link:
            continue

        retailer = normalize_retailer(seller or "")
        out.append({
            "name": name,
            "price": float(price),
            "currency": "SAR",
            "retailer": retailer,
            "link": link,
            "image": thumb,
            "condition": cond or "",
            "source": "searchapi_google_shopping",
        })
    return out


def product_page_fetch(url: str) -> Dict[str, Any]:
    """Fetch page HTML and try to extract clarified specs (placeholder heuristics)."""
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {"ok": False, "error": str(e)}

    model = None
    if re.search(r"15\s*Pro\s*Max", html, re.I):
        model = "iPhone 15 Pro Max"
    elif re.search(r"15\s*Pro\b", html, re.I):
        model = "iPhone 15 Pro"

    storage = None
    if re.search(r"(256)\s*GB|٢٥٦", html, re.I):
        storage = "256GB"

    return {"ok": True, "model": model, "storage": storage}
