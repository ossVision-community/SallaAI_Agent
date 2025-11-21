# app/core/config.py
from __future__ import annotations

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env at backend root
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY")


def get_openai_client() -> OpenAI:
    """Return a shared OpenAI client. Raises if API key is missing."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing (set env var or .env).")
    return OpenAI(api_key=OPENAI_API_KEY)


# Global OpenAI client (used by ranking module)
client: OpenAI = get_openai_client()
