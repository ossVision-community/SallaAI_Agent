from __future__ import annotations

import json
from typing import Any, Dict

from Core.config import client


INTENT_SYSTEM_PROMPT = """You are a premium shopping concierge for Saudi Arabia. Your job is to find THE PERFECT product, not just any product.

## YOUR BEHAVIOR: Act like a personal shopper, NOT a search engine
- ASK clarifying questions to understand user needs deeply
- Only proceed to search when you have enough info to make a GREAT recommendation

## search_query Field (when ready=true)
- Clean product search term: "Samsung TV 55 inch 4K", "iPhone 15 Pro Max 256GB"
- NEVER use conversational text
- Include specific details from the conversation

## ready Field Logic - BE A CONCIERGE, NOT A SEARCH BOX

Set ready=FALSE and ask follow_up_question if user hasn't specified:
- Budget range (essential for good recommendations)
- Key preference (brand, size, specific features)
- Use case (gaming TV? work laptop? gift phone?)

Set ready=TRUE only when:
- User explicitly says "no preference", "any budget", "doesn't matter"  
- User provides budget AND at least one preference (brand/size/use)
- User insists: "just show me something", "I don't care"

## Examples:
User: "I need TV" → ready=false, follow_up: "What's your budget? And what size works for your room?"
User: "TV for my room 4*4" → ready=false, follow_up: "Great, a 43-50 inch would fit well. What's your budget?"
User: "TV, budget 2000 SAR" → ready=true, search_query: "TV 50 inch" (infer size)
User: "TV 2000 SAR, any size" → ready=true, search_query: "TV 4K smart"
User: "just give me any TV" → ready=true, search_query: "TV 43 inch budget"

## Language: Match user's language (English→English, Arabic→Arabic)

Respond with strict JSON."""


def analyze_intent(query: str) -> Dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "need_summary": {"type": "string"},
            "category": {"type": "string"},
            "search_query": {"type": "string"},
            "budget_min": {"type": ["number", "null"]},
            "budget_max": {"type": ["number", "null"]},
            "must_have": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "nice_to_have": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "missing_info": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "follow_up_question": {"type": ["string", "null"]},
            "ready": {"type": "boolean"},
        },
        "required": [
            "need_summary",
            "category",
            "search_query",
            "budget_min",
            "budget_max",
            "must_have",
            "nice_to_have",
            "missing_info",
            "follow_up_question",
            "ready",
        ],
    }

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User request: {query}\n\n"
                    "Extract a clean product search_query (NO conversational text). "
                    "Respond with JSON."
                ),
            },
        ],
    )
    data = json.loads(resp.choices[0].message.content)

    # Normalize legacy fields (some models might return different keys)
    if "ready" not in data:
        data["ready"] = bool(data.get("enough_information"))
    if "missing_info" not in data and "missing_details" in data:
        data["missing_info"] = data.get("missing_details", [])

    # Ensure defaults
    data.setdefault("must_have", [])
    data.setdefault("nice_to_have", [])
    data.setdefault("missing_info", [])

    # REMOVED: Forced ready=True if missing_info is empty.
    # We now trust the LLM to decide if it needs more info even if it didn't list specific "missing keys" yet.
    
    # Normalize follow-up question empty strings to None
    fq = data.get("follow_up_question")
    data["follow_up_question"] = fq.strip() if isinstance(fq, str) and fq.strip() else None

    return data

