# src/tools/symbol_lookup.py

import re
import requests
from urllib.parse import quote_plus
from src.config import FINNHUB_API_KEY

def _clean_query(user_query: str) -> str:
    """
    Convert 'stock price of HDFCBank' -> 'HDFCBank'
    Remove extra keywords so Finnhub /search works properly.
    """
    q = user_query.lower().strip()

    # remove common filler words
    q = re.sub(r"\b(stock|share|price|of|give|me|today|current|latest)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    # keep only letters/numbers/spaces
    q = re.sub(r"[^a-zA-Z0-9\s&.-]", "", q).strip()

    # fallback if empty
    return q if q else user_query.strip()

def symbol_lookup(user_query: str) -> dict:
    query = _clean_query(user_query)
    url = f"https://finnhub.io/api/v1/search?q={quote_plus(query)}&token={FINNHUB_API_KEY}"

    r = requests.get(url, timeout=10)

    # ✅ Better error message
    if r.status_code != 200:
        return {
            "error": True,
            "status_code": r.status_code,
            "query_used": query,
            "response_text": r.text
        }

    return r.json()
