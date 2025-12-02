# app/agent/graph.py
from __future__ import annotations

import json
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
# لا نستخدم MemorySaver عشان ما نحتاج thread_id
# from langgraph.checkpoint.memory import MemorySaver

from Core.constants import TRUSTED_KSA
from Agent.tools import shopping_search, product_page_fetch
from Agent.normalizers import spec_normalizer, price_normalizer, batch_spec_normalizer
from Agent.ranking import llm_rank_offers
from Agent.intent import analyze_intent


class AgentState(TypedDict, total=False):
    query: str
    offers: List[Dict[str, Any]]
    missing: List[str]
    tried_tools: List[str]
    steps: int
    done: bool
    errors: List[str]
    next_tool: Dict[str, Any]
    trusted_only: bool
    intent: Dict[str, Any]
    needs_more_info: bool
    follow_up_question: Optional[str]
    search_query: str
    clarification_count: int
    result: Dict[str, Any]  # Final output with items and notes


# -----------------------------
# Planner
# -----------------------------
def planner(state: AgentState) -> AgentState:
    """Decide next tool based on current state."""
    q = state.get("query", "")
    steps = state.get("steps", 0)
    tried = set(state.get("tried_tools", []))
    offers = state.get("offers", [])

    intent = state.get("intent")
    if not intent:
        intent = analyze_intent(q)
        state["intent"] = intent
        state["search_query"] = intent.get("search_query", q)
        if not intent.get("ready", False):
            clarifications = state.get("clarification_count", 0)
            if clarifications >= 1:
                # already asked once; proceed with best effort
                intent["ready"] = True
                intent["follow_up_question"] = None
                state["needs_more_info"] = False
                state["follow_up_question"] = None
            else:
                state["needs_more_info"] = True
                state["follow_up_question"] = intent.get("follow_up_question")
                state["clarification_count"] = clarifications + 1
                state["done"] = True
                return state
        # ready now -> ensure flags cleared
        state["needs_more_info"] = False
        state["follow_up_question"] = None

    # Enforce max of 5 tool steps (roughly 5 agent messages)
    if steps >= 5:
        state["done"] = True
        state["needs_more_info"] = False  # Ensure we don't get stuck in a loop if we hit step limit
        return state

    # If we already tried shopping_search and got nothing → stop
    if "shopping_search" in tried and not offers:
        state["done"] = True
        state.setdefault("errors", []).append("No offers found from shopping_search")
        return state

    # First tool: shopping_search
    search_query = state.get("search_query", q)

    if "shopping_search" not in tried:
        state["next_tool"] = {
            "name": "shopping_search",
            "args": {"query": search_query, "limit": 40},
        }
        return state

    # Run spec_normalizer for richer metadata
    if offers and "spec_normalizer_batch" not in tried:
        state["next_tool"] = {"name": "spec_normalizer_batch", "args": {}}
        return state

    # Optionally enrich by fetching product pages if we still lack details
    if offers and "product_page_fetch_batch" not in tried:
        urls = [o.get("link") for o in offers[:3] if o.get("link")]
        if urls:
            state["next_tool"] = {"name": "product_page_fetch_batch", "args": {"urls": urls}}
            return state

    # Normalize prices to SAR if needed
    if offers and any("price_sar" not in o for o in offers) and "price_normalizer_batch" not in tried:
        state["next_tool"] = {"name": "price_normalizer_batch", "args": {}}
        return state

    # Nothing else to do → finish or enforce max messages (5 steps)
    if steps >= 5:
        state["done"] = True
    else:
        state["done"] = True
    return state


# -----------------------------
# Actor
# -----------------------------
def actor(state: AgentState) -> AgentState:
    """Execute the selected tool."""
    nxt = state.get("next_tool", {})
    name = nxt.get("name")
    args = nxt.get("args", {})
    state.setdefault("tried_tools", []).append(name or "none")

    try:
        if name == "shopping_search":
            res = shopping_search(**args)
            state.setdefault("offers", []).extend(res)

        elif name == "spec_normalizer_batch":
            offers = state.get("offers", [])
            if offers:
                items_to_norm = [
                    {
                        "name": o.get("name", ""),
                        "retailer": o.get("retailer", ""),
                        "condition": o.get("condition", "")
                    }
                    for o in offers
                ]
                normalized_list = batch_spec_normalizer(items_to_norm)
                for o, norm in zip(offers, normalized_list):
                    o.update(norm)

        elif name == "product_page_fetch_batch":
            # Safe fetch wrapper
            def safe_fetch(u):
                try:
                    return product_page_fetch(u)
                except Exception:
                    return {"ok": False}

            url_map = {u: safe_fetch(u) for u in args.get("urls", [])}
            for o in state.get("offers", []):
                u = o.get("link")
                if u in url_map and url_map[u].get("ok"):
                    if url_map[u].get("model"):
                        o["model"] = url_map[u]["model"]
                    if url_map[u].get("storage"):
                        o["storage"] = url_map[u]["storage"]

        elif name == "price_normalizer_batch":
            for o in state.get("offers", []):
                normp = price_normalizer(o.get("price", 0.0), o.get("currency"))
                o.update(normp)

    except Exception as e:
        state.setdefault("errors", []).append(f"{name}: {e}")

    return state


# -----------------------------
# Observer
# -----------------------------
def observer(state: AgentState) -> AgentState:
    """Update bookkeeping after each tool call."""
    state["steps"] = state.get("steps", 0) + 1

    # Deduplicate offers by link
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for o in state.get("offers", []):
        lk = o.get("link")
        if lk and lk not in seen:
            seen.add(lk)
            deduped.append(o)
    state["offers"] = deduped

    # Remove transient key
    state.pop("next_tool", None)
    return state


# -----------------------------
# Finisher
# -----------------------------
def finisher(state: AgentState) -> Dict[str, Any]:
    """
    Final node:
    - Filter candidates
    - Prefer trusted sellers
    - Call LLM re-ranker
    - Store result in state["result"]
    - Return the updated state
    """
    q = state.get("query", "")
    offers = state.get("offers", [])
    trusted_only = bool(state.get("trusted_only"))

    if state.get("needs_more_info"):
        question = state.get("follow_up_question")
        state["result"] = {
            "items": [],
            "notes": question or "أحتاج مزيداً من التفاصيل لمساعدتك.",
        }
        return state

    intent = state.get("intent", {})

    def pass_basic(o: Dict[str, Any]) -> bool:
        """Basic validation - only check essential fields exist."""
        price_val = o.get("price_sar", o.get("price"))
        link = o.get("link")
        
        # Only reject if missing essential data
        if not link or price_val is None:
            return False
        try:
            float(price_val)
        except Exception:
            return False
        return True

    # Let LLM ranker handle smart filtering - don't over-filter here
    candidates = [o for o in offers if pass_basic(o)]

    def is_trusted(o: Dict[str, Any]) -> bool:
        return o.get("retailer") in TRUSTED_KSA

    trusted_candidates = [c for c in candidates if is_trusted(c)]

    # Case 1: user wants trusted_only and there is no trusted candidate
    if trusted_only and not trusted_candidates:
        state["errors"] = state.get("errors", []) + ["No trusted offers found"]
        state["result"] = {
            "items": [],
            "notes": "No trusted KSA offers matched the query.",
        }
        return state

    # Base set for ranking
    base = trusted_candidates if (trusted_only and trusted_candidates) else candidates or offers

    # If still no candidates at all, but offers exist, fall back to raw offers
    if not base and offers:
        base = offers[:5]

    if not base:
        state["result"] = {
            "items": [],
            "notes": "No matching offers found after filtering.",
        }
        return state

    def cond_rank(c: str) -> int:
        """Rank conditions: New < Refurbished < Used < Unknown."""
        c = (c or "").lower()
        if c.startswith("new"):
            return 0
        if c.startswith("refurb"):
            return 1
        if c.startswith("used"):
            return 2
        return 3

    # Local pre-sort before LLM
    base.sort(
        key=lambda x: (
            0 if is_trusted(x) else 1,
            cond_rank(x.get("condition")),
            float(x.get("price_sar", x.get("price", 9e9))),
        )
    )

    # LLM picks THE BEST product (not a list)
    try:
        ranked = llm_rank_offers(base[:20], q, intent=intent, trusted_only=trusted_only, top_k=1)
        state["result"] = {
            "items": ranked.get("items", []),
            "notes": ranked.get("notes"),
        }
    except Exception as e:
        state.setdefault("errors", []).append(f"Ranking failed: {e}")
        # Fallback: return first offer as-is
        if base:
            state["result"] = {
                "items": [{
                    "name": base[0].get("name"),
                    "price": base[0].get("price_sar", base[0].get("price")),
                    "currency": "SAR",
                    "retailer": base[0].get("retailer"),
                    "link": base[0].get("link"),
                    "reason": "Best available option",
                }],
                "notes": None,
            }
        else:
            state["result"] = {"items": [], "notes": "Ranking failed"}
    
    state["needs_more_info"] = False
    return state

# -----------------------------
# Build Graph
# -----------------------------
def build_app():
    """Build and compile the LangGraph app."""
    graph = StateGraph(AgentState)

    graph.add_node("plan", planner)
    graph.add_node("act", actor)
    graph.add_node("observe", observer)
    graph.add_node("finish", finisher)

    graph.add_edge(START, "plan")

    def route_after_plan(state: AgentState):
        return "finish" if state.get("done") else "act"

    def route_after_act(state: AgentState):
        return "observe"

    def route_after_observe(state: AgentState):
        return "plan"

    graph.add_conditional_edges("plan", route_after_plan, {"finish": "finish", "act": "act"})
    graph.add_conditional_edges("act", route_after_act, {"observe": "observe"})
    graph.add_conditional_edges("observe", route_after_observe, {"plan": "plan"})
    graph.add_edge("finish", END)

    # بدون checkpointer
    app = graph.compile()
    return app
