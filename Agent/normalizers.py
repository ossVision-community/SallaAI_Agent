# app/agent/normalizers.py
from __future__ import annotations

import json
from typing import Dict, Any, Optional, List

from Core.config import client

def price_normalizer(price: float, currency: Optional[str]) -> Dict[str, Any]:
    """Normalize a price to SAR. If currency unknown, assume SAR."""
    if not currency or currency.upper() == "SAR":
        return {"price_sar": float(price), "currency": "SAR"}

    # Basic placeholder rates - in a real agent, use a live currency API
    rates = {"USD": 3.75, "EUR": 4.1, "AED": 1.02}
    factor = rates.get(currency.upper(), 1.0)
    return {"price_sar": float(price) * factor, "currency": currency.upper()}


def batch_spec_normalizer(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize a batch of product items using LLM to extract structured specs.
    
    Args:
        items: List of dicts containing 'name', 'retailer', 'condition' (optional)
        
    Returns:
        List of dicts with normalized 'model', 'storage', 'condition', 'brand', etc.
        The order matches the input list.
    """
    if not items:
        return []

    # Prepare a minimized list for the LLM to reduce token usage
    prompt_items = []
    for i, item in enumerate(items):
        txt = f"{item.get('name', '')} {item.get('retailer', '')} {item.get('condition', '')}"
        prompt_items.append({"id": i, "text": txt.strip()})

    system_prompt = (
        "You are a product data normalization expert. "
        "Extract key specifications from the provided product text strings. "
        "Return a JSON object with a 'results' list, where each item has: "
        "'id' (int), 'brand' (str), 'model' (str, normalized), 'storage' (str, e.g. '256GB' or null), "
        "and 'condition' (str, normalized to 'New', 'Used', 'Refurbished', or 'Unknown'). "
        "Handle Arabic text and varied formats intelligently."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        results_map = {r["id"]: r for r in data.get("results", [])}
        
        # Reassemble in order
        final_output = []
        for i in range(len(items)):
            extracted = results_map.get(i, {})
            final_output.append({
                "brand": extracted.get("brand"),
                "model": extracted.get("model"),
                "storage": extracted.get("storage"),
                "condition": extracted.get("condition", "Unknown")
            })
            
        return final_output

    except Exception as e:
        # Fallback if LLM fails: return empty specs so the flow doesn't break
        print(f"Error in batch_spec_normalizer: {e}")
        return [{"model": None, "storage": None, "condition": "Unknown"} for _ in items]


def spec_normalizer(name: str, retailer: str, condition: str) -> Dict[str, Any]:
    """
    Single item wrapper for compatibility, but less efficient than batch.
    Prefer using batch_spec_normalizer.
    """
    items = [{"name": name, "retailer": retailer, "condition": condition}]
    results = batch_spec_normalizer(items)
    return results[0] if results else {"model": None, "storage": None, "condition": "Unknown"}
