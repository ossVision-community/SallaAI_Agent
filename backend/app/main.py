# app/main.py
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import OPENAI_API_KEY
from app.api.v1.routes_rank import router as rank_router


app = FastAPI(
    title="KSA Shopping Ranker API",
    description="LangGraph-based shopping agent for the Saudi market.",
    version="0.1.0",
)

# CORS (you can restrict origins later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Simple health check endpoint."""
    if not OPENAI_API_KEY:
        return {
            "status": "error",
            "message": "OPENAI_API_KEY is missing",
        }
    return {
        "status": "ok",
        "service": "KSA Shopping Ranker API",
        "version": "0.1.0",
    }


# Register v1 routes
app.include_router(rank_router)
