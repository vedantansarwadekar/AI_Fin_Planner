# src/tools/market.py

import requests
from src.config import FINNHUB_API_KEY

def get_stock_price(symbol: str):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    r = requests.get(url, timeout=10)

    # ✅ Don’t crash the app on forbidden/unauthorized
    if r.status_code != 200:
        return {
            "error": True,
            "status_code": r.status_code,
            "symbol": symbol,
            "message": "Finnhub access denied for this symbol/market (likely plan limitation).",
            "response_text": r.text
        }

    data = r.json()

    return {
        "symbol": symbol,
        "current": data.get("c"),
        "high": data.get("h"),
        "low": data.get("l"),
        "open": data.get("o"),
        "prev_close": data.get("pc"),
    }
