# src/tools/market.py
"""
Stock price and news data.

Indian stocks:  Yahoo Finance (free, no API key needed, NSE/BSE supported)
US stocks:      Finnhub → fallback to Yahoo Finance
News:           Finnhub → fallback to web search

Indian ticker format on Yahoo Finance:
  NSE stocks → append .NS  (e.g. RELIANCE.NS, HDFCBANK.NS, TCS.NS)
  BSE stocks → append .BO  (e.g. RELIANCE.BO)
"""

import re
import requests
from datetime import date, timedelta, datetime
from src.config import FINNHUB_API_KEY

# ── Helpers ───────────────────────────────────────────────────────────────────

INDIAN_EXCHANGE_SUFFIXES = [".NS", ".BO"]

# Common Indian company → NSE ticker mapping
# Handles casual names users actually type
INDIAN_TICKER_MAP = {
    "reliance":         "RELIANCE.NS",
    "tcs":              "TCS.NS",
    "tata consultancy": "TCS.NS",
    "infosys":          "INFY.NS",
    "infy":             "INFY.NS",
    "hdfc bank":        "HDFCBANK.NS",
    "hdfcbank":         "HDFCBANK.NS",
    "hdfc":             "HDFCBANK.NS",
    "icici bank":       "ICICIBANK.NS",
    "icicibank":        "ICICIBANK.NS",
    "icici":            "ICICIBANK.NS",
    "wipro":            "WIPRO.NS",
    "sbi":              "SBIN.NS",
    "state bank":       "SBIN.NS",
    "bajaj finance":    "BAJFINANCE.NS",
    "bajajfinance":     "BAJFINANCE.NS",
    "kotak":            "KOTAKBANK.NS",
    "kotak bank":       "KOTAKBANK.NS",
    "axis bank":        "AXISBANK.NS",
    "axisbank":         "AXISBANK.NS",
    "maruti":           "MARUTI.NS",
    "maruti suzuki":    "MARUTI.NS",
    "ongc":             "ONGC.NS",
    "adani":            "ADANIENT.NS",
    "adani enterprises":"ADANIENT.NS",
    "adani ports":      "ADANIPORTS.NS",
    "adani green":      "ADANIGREEN.NS",
    "adani power":      "ADANIPOWER.NS",
    "titan":            "TITAN.NS",
    "asian paints":     "ASIANPAINT.NS",
    "nestle":           "NESTLEIND.NS",
    "hindustan unilever":"HINDUNILVR.NS",
    "hul":              "HINDUNILVR.NS",
    "itc":              "ITC.NS",
    "ltimindtree":      "LTIM.NS",
    "lti":              "LTIM.NS",
    "tech mahindra":    "TECHM.NS",
    "techmahindra":     "TECHM.NS",
    "sun pharma":       "SUNPHARMA.NS",
    "sunpharma":        "SUNPHARMA.NS",
    "cipla":            "CIPLA.NS",
    "dr reddy":         "DRREDDY.NS",
    "ultratech":        "ULTRACEMCO.NS",
    "ultratech cement": "ULTRACEMCO.NS",
    "tata motors":      "TATAMOTORS.NS",
    "tatamotors":       "TATAMOTORS.NS",
    "tata steel":       "TATASTEEL.NS",
    "tatasteel":        "TATASTEEL.NS",
    "bharti airtel":    "BHARTIARTL.NS",
    "airtel":           "BHARTIARTL.NS",
    "bajaj auto":       "BAJAJ-AUTO.NS",
    "hero motocorp":    "HEROMOTOCO.NS",
    "m&m":              "M&M.NS",
    "mahindra":         "M&M.NS",
    "power grid":       "POWERGRID.NS",
    "ntpc":             "NTPC.NS",
    "coal india":       "COALINDIA.NS",
    "divis":            "DIVISLAB.NS",
    "nifty":            "^NSEI",
    "sensex":           "^BSESN",
    "nifty 50":         "^NSEI",
}


def _resolve_indian_ticker(query: str) -> str | None:
    """Map a company name or ticker to Yahoo Finance format."""
    q = query.lower().strip()
    # Direct map lookup
    for key, ticker in INDIAN_TICKER_MAP.items():
        if key in q:
            return ticker
    # If it looks like a raw NSE ticker (all caps, no suffix)
    raw = query.upper().strip()
    if re.match(r'^[A-Z&\-]{2,15}$', raw) and raw not in {"IPO","NSE","BSE","STOCK"}:
        return f"{raw}.NS"
    return None


def _yahoo_quote(ticker: str) -> dict:
    """Fetch quote from Yahoo Finance (no API key needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return {"error": True, "message": f"Yahoo Finance returned {r.status_code}"}

        data  = r.json()
        meta  = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev  = meta.get("chartPreviousClose") or meta.get("previousClose")
        currency = meta.get("currency", "INR")
        name     = meta.get("longName") or meta.get("shortName") or ticker

        change     = round(price - prev, 2) if price and prev else None
        change_pct = round((change / prev) * 100, 2) if change and prev else None

        return {
            "symbol":       ticker,
            "name":         name,
            "current":      price,
            "prev_close":   prev,
            "change":       change,
            "change_pct":   change_pct,
            "currency":     currency,
            "high":         meta.get("regularMarketDayHigh"),
            "low":          meta.get("regularMarketDayLow"),
            "open":         meta.get("regularMarketOpen"),
            "52w_high":     meta.get("fiftyTwoWeekHigh"),
            "52w_low":      meta.get("fiftyTwoWeekLow"),
            "market_cap":   meta.get("marketCap"),
            "exchange":     meta.get("exchangeName", ""),
            "source":       "Yahoo Finance",
            "as_of":        datetime.now().strftime("%d %b %Y %H:%M IST"),
        }
    except Exception as e:
        return {"error": True, "message": f"Yahoo Finance error: {e}"}


def _finnhub_quote(symbol: str) -> dict:
    """Fetch quote from Finnhub (US stocks, requires API key)."""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {"error": True, "message": f"Finnhub returned {r.status_code}"}
        d = r.json()
        price = d.get("c")
        prev  = d.get("pc")
        change     = round(price - prev, 2) if price and prev else None
        change_pct = round((change / prev) * 100, 2) if change and prev else None
        return {
            "symbol":     symbol,
            "current":    price,
            "prev_close": prev,
            "change":     change,
            "change_pct": change_pct,
            "high":       d.get("h"),
            "low":        d.get("l"),
            "open":       d.get("o"),
            "currency":   "USD",
            "source":     "Finnhub",
            "as_of":      datetime.now().strftime("%d %b %Y %H:%M UTC"),
        }
    except Exception as e:
        return {"error": True, "message": f"Finnhub error: {e}"}


# ── Public API ────────────────────────────────────────────────────────────────

def get_stock_price(query: str) -> dict:
    """
    Get live stock price for Indian or US stocks.

    For Indian stocks (NSE/BSE): uses Yahoo Finance — no API key needed.
    For US stocks: tries Finnhub first, then Yahoo Finance.

    Args:
        query: Company name ("Reliance", "HDFC Bank") or ticker ("TCS", "AAPL")

    Returns:
        Dict with price data, or {"error": True, "message": "..."}
    """
    # Try Indian ticker first
    indian_ticker = _resolve_indian_ticker(query)
    if indian_ticker:
        result = _yahoo_quote(indian_ticker)
        if not result.get("error"):
            return result
        # Try .BO suffix if .NS failed
        if indian_ticker.endswith(".NS"):
            result2 = _yahoo_quote(indian_ticker.replace(".NS", ".BO"))
            if not result2.get("error"):
                return result2

    # Try as US ticker via Finnhub
    raw_ticker = query.upper().strip().split()[0]
    finnhub_result = _finnhub_quote(raw_ticker)
    if not finnhub_result.get("error") and finnhub_result.get("current"):
        return finnhub_result

    # Final fallback: Yahoo Finance with raw ticker
    yahoo_result = _yahoo_quote(raw_ticker)
    if not yahoo_result.get("error"):
        return yahoo_result

    return {
        "error":   True,
        "query":   query,
        "message": (
            f"Could not find price for '{query}'. "
            "Try the exact NSE ticker (e.g. RELIANCE, HDFCBANK, TCS) "
            "or US ticker (e.g. AAPL, TSLA)."
        )
    }


def get_company_news(symbol: str, days: int = 7) -> list[dict]:
    """
    Get recent company news. Tries Finnhub, returns structured list.
    """
    to_date   = date.today()
    from_date = to_date - timedelta(days=days)

    # Strip Yahoo suffixes for Finnhub
    clean_symbol = symbol.replace(".NS", "").replace(".BO", "")

    try:
        url = (
            f"https://finnhub.io/api/v1/company-news"
            f"?symbol={clean_symbol}&from={from_date}&to={to_date}"
            f"&token={FINNHUB_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                return [
                    {
                        "headline": item.get("headline"),
                        "source":   item.get("source"),
                        "url":      item.get("url"),
                        "summary":  item.get("summary"),
                        "date":     datetime.fromtimestamp(
                            item.get("datetime", 0)
                        ).strftime("%d %b %Y") if item.get("datetime") else "",
                    }
                    for item in data[:6]
                ]
    except Exception:
        pass

    # Fallback: web search for news
    from src.tools.web_search import web_search
    return web_search(f"{symbol} company news latest")