# KSA Shopping Agent – Backend (FastAPI + LangGraph)

This system provides an AI-powered shopping agent optimized for the Saudi market.  
It uses LangGraph, OpenAI, and SearchAPI.io (Google Shopping) to search for products, normalize specs, and recommend the best offers according to a clear policy.

## Overview

- **Tech stack**
  - Python 3.12+
  - FastAPI
  - LangGraph
  - OpenAI API
  - SearchAPI.io (Google Shopping)
  - dotenv / requests

- **Core idea**
  - Given a free-text query (e.g. `"iPhone 17 Pro 256GB"` or `"27 inch 2K monitor"`),
  - The agent calls Google Shopping via SearchAPI.io,
  - Normalizes retailers, specs, and prices,
  - Applies a KSA-focused selection policy,
  - Optionally prefers *trusted Saudi retailers* (Jarir, Extra, Noon, Amazon.sa, Apple Store, etc.),
  - Returns a clean JSON with the top recommended items and links.

This Agent is designed to be consumed later by a web or mobile frontend, or by a higher-level conversational `/chat` endpoint.

---

## Features

- Search any product supported by Google Shopping (phones, screens, laptops, etc.).
- Selection policy:
  - Prefer trusted KSA retailers (Jarir, Extra, Noon, Amazon.sa, Apple Store…).
  - Prefer **New** > **Refurbished** > **Used** > **Unknown** condition.
  - Then sort by lowest price in SAR.
- Normalization:
  - Retailer name normalization (e.g. `"جرير"` → `"Jarir"`).
  - Basic spec extraction (model, storage, condition).
  - Price normalization to SAR (simple placeholder FX for non-SAR).
- LangGraph agent:
  - Plan → Act → Observe → Finish flow.
  - Uses internal tools:
    - `shopping_search` (SearchAPI.io wrapper).
    - `spec_normalizer_batch`.
    - `price_normalizer_batch`.
- FastAPI endpoint:
  - `POST /rank` – main agent endpoint.

---


