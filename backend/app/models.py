# app/models.py (تكملة)

from typing import List, Literal
from pydantic import BaseModel

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatTurn]

class ChatResponse(BaseModel):
    reply: str
    done: bool
    cheapest_item: dict | None = None
