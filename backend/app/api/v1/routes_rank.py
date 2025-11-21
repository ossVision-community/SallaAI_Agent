# app/api/v1/routes_rank.py
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.agent import build_app, AgentState
from app.core.config import OPENAI_API_KEY
from .schemas import RankRequest, RankResponse, RankResult, OfferItem

router = APIRouter(prefix="/rank", tags=["rank"])

# Build LangGraph app once per process
agent_app = build_app()


@router.post("", response_model=RankResponse)
async def rank_products(payload: RankRequest) -> RankResponse:
    """
    Main endpoint:
    - Accepts a query (e.g. 'iPhone 15 Pro Max 256GB').
    - Optionally restricts to trusted KSA retailers.
    - Runs the LangGraph agent and returns ranked offers.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing (set env var).")

    init_state: AgentState = {
        "query": payload.query,
        "offers": [],
        "missing": [],
        "tried_tools": [],
        "steps": 0,
        "done": False,
        "errors": [],
        "trusted_only": bool(payload.trusted_only),
    }

    final: Dict[str, Any] | None = None

    # Run the LangGraph agent and capture the final state
    for event in agent_app.stream(init_state):
        for node, node_payload in event.items():
            if node == "finish":
                # node_payload is what finisher() returned
                final = node_payload

    if final is None:
        raise HTTPException(status_code=500, detail="Agent did not reach finish node.")

    # Debug: print final to console (useful الآن عشان تشوف شلون شكله)
    print("\n[FINAL STATE FROM AGENT]")
    try:
        import json
        print(json.dumps(final, ensure_ascii=False, indent=2))
    except Exception:
        print(final)

    # ---- Normalize the shape for RankResponse ----

    # Basic fields
    query = final.get("query", payload.query)
    steps = int(final.get("steps", 0))
    errors = final.get("errors", []) or []

    # result block:
    # - إذا finisher رجّع {"query", "steps", "errors", "result": {...}} → نأخذ result
    # - إذا رجّع مباشرة {"items": [...], "notes": "..."} → نستخدمه كـ result
    result_block: Dict[str, Any] = final.get("result", final)

    raw_items = result_block.get("items", []) or []
    notes = result_block.get("notes")

    # Map raw items إلى OfferItem (Pydantic) مع defaultات
    items: list[OfferItem] = []
    for it in raw_items:
        # نضمن الحقول الأساسية لو ناقصة
        item = OfferItem(
            name=str(it.get("name", "")),
            price=float(it.get("price", 0.0)),
            currency=str(it.get("currency", "SAR")),
            retailer=str(it.get("retailer", "")),
            link=str(it.get("link", "")),
            condition=it.get("condition"),
            reason=it.get("reason"),
        )
        items.append(item)

    result = RankResult(items=items, notes=notes)

    # Build final Pydantic response
    response = RankResponse(
        query=query,
        steps=steps,
        errors=errors,
        result=result,
    )
    return response
