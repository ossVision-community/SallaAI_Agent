# app/agent/ranking.py
from __future__ import annotations

import json
from typing import List, Dict, Any

from app.core.config import client
from app.core.constants import TRUSTED_KSA


def is_pro_max_query(q: str) -> bool:
    """Return True if the query suggests 'Pro Max' model."""
    q = q.lower()
    return any(k in q for k in ["pro max", "promax", "ماكس", "max"])


def need_256(q: str) -> bool:
    """Return True if the query explicitly mentions 256GB."""
    q = q.lower()
    return ("256" in q) or ("٢٥٦" in q)


def llm_rank_offers(
    offers: List[Dict[str, Any]],
    query: str,
    top_k: int = 4,
) -> Dict[str, Any]:
    """Final LLM re-ranking with policy-aware selection and JSON output."""
    slim = [
        {
            "name": o.get("name"),
            "price": o.get("price_sar", o.get("price")),
            "currency": "SAR",
            "retailer": o.get("retailer"),
            "link": o.get("link"),
            "condition": o.get("condition"),
        }
        for o in offers
        if o.get("link")
    ]

    policy = {
        "primary_match": {
            "must_match_model": "iPhone 15 Pro Max" if is_pro_max_query(query) else "iPhone 15 Pro",
            "must_match_storage": "256GB" if need_256(query) else "any",
        },
        "prefer": {
            "condition_order": ["New", "Refurbished", "Used", "Unknown"],
            "retailer_trust_bonus_names": sorted(list(TRUSTED_KSA)),
            "currency": "SAR",
        },
        "avoid": ["ambiguous bundles", "non-KSA results if local exists"],
        "tie_breakers": ["lower price", "return window", "seller reputation"],
    }

    system = (
        "You are a KSA e-commerce expert. Given JSON results, pick best matching offers "
        "(exact model/storage), prefer trusted local retailers, prefer New, then lowest price. "
        "Return strict JSON only."
    )
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "price", "currency", "retailer", "link", "reason"],
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                        "currency": {"type": "string"},
                        "retailer": {"type": "string"},
                        "link": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "notes": {"type": "string"},
        },
        "required": ["items"],
    }

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Query:\n" + query +
                    "\n\nPolicy:\n" + json.dumps(policy, ensure_ascii=False) +
                    "\n\nResults:\n" + json.dumps(slim, ensure_ascii=False) +
                    "\n\nReturn schema:\n" + json.dumps(schema, ensure_ascii=False)
                ),
            },
        ],
    )
    data = json.loads(resp.choices[0].message.content)
    data["items"] = data.get("items", [])[:top_k]
    return data
