# app/api/v1/schemas.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class RankRequest(BaseModel):
    """Request body for ranking products based on a natural language query."""
    query: str
    trusted_only: bool = True


class OfferItem(BaseModel):
    """Single ranked offer returned by the agent."""
    name: str
    price: float
    currency: str
    retailer: str
    link: str
    condition: Optional[str] = None
    reason: Optional[str] = None


class RankResult(BaseModel):
    """LLM ranking result."""
    items: List[OfferItem] = []
    notes: Optional[str] = None


class RankResponse(BaseModel):
    """Full response returned by the API."""
    query: str
    steps: int
    errors: List[str] = []
    result: RankResult
