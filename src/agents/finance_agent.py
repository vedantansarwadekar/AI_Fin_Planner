# src/agents/finance_agent.py

import re
from typing import Optional

from src.llm import get_llm
from src.tools.web_search import web_search
from src.tools.market import get_stock_price
from src.tools.news import get_company_news
from src.tools.budget_calc import budget_plan
from src.tools.symbol_lookup import symbol_lookup


# ✅ Anything current/latest/upcoming should go to web search to avoid outdated LLM answers
TIME_SENSITIVE = [
    "ipo",
    "upcoming",
    "new ipo",
    "repo rate",
    "interest rate",
    "latest",
    "today",
    "current",
    "deadline",
    "update",
    "announcement",
    "new rules",
]


# -----------------------------
# Helpers
# -----------------------------

def extract_ticker(text: str) -> Optional[str]:
    """
    Extract tickers like MSFT/AAPL/TSLA if user typed them directly.
    """
    tickers = re.findall(r"\b[A-Z]{2,10}\b", text.upper())
    blacklist = {"IPO", "INDIA", "NSE", "BSE", "STOCK", "SHARE", "PRICE", "RATE", "RBI"}
    tickers = [t for t in tickers if t not in blacklist]
    return tickers[-1] if tickers else None


def clean_company_query(user_query: str) -> str:
    """
    Finnhub /search expects a clean query like 'HDFCBank', not:
    'stock price of HDFCBank'
    """
    q = user_query.lower().strip()

    # Remove common filler words
    q = re.sub(r"\b(stock|share|price|of|give|me|today|current|latest|pls|please)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    # Keep only letters/numbers/spaces/&/./-
    q = re.sub(r"[^a-zA-Z0-9\s&.-]", "", q).strip()

    return q if q else user_query.strip()


def parse_indian_amount(text: str) -> Optional[int]:
    """
    Parse:
    - 2 lakh -> 200000
    - 1.5 lakh -> 150000
    - 3 crore -> 30000000
    - 200000 -> 200000
    """
    t = text.lower().replace(",", "").strip()

    match = re.search(r"(\d+(\.\d+)?)\s*(lakh|lakhs|crore|crores)", t)
    if match:
        num = float(match.group(1))
        unit = match.group(3)
        if "lakh" in unit:
            return int(num * 100000)
        if "crore" in unit:
            return int(num * 10000000)

    digits = re.findall(r"\d+", t)
    if digits:
        return int(digits[0])

    return None


def extract_months(text: str) -> Optional[int]:
    """
    Extract months like: '10 months'
    """
    match = re.search(r"(\d+)\s*(month|months|mths)", text.lower())
    if match:
        return int(match.group(1))
    return None


def fallback_symbol_from_web(company_query: str) -> str:
    """
    If Finnhub symbol lookup fails, use Tavily web search to guess ticker.
    Less accurate, but a good backup.
    """
    try:
        results = web_search(f"{company_query} ticker symbol")
        blob = str(results).upper()

        direct = extract_ticker(company_query)
        if direct:
            return direct

        candidates = re.findall(r"\b[A-Z]{2,12}\b", blob)

        blacklist = {
            "IPO", "INDIA", "NSE", "BSE", "STOCK", "SHARE", "PRICE", "LIMITED",
            "LTD", "PLC", "THE", "AND", "FOR", "WITH", "COMPANY", "SYMBOL",
            "TICKER", "QUOTE", "MARKET", "TODAY"
        }

        for t in candidates:
            if t in blacklist:
                continue
            if 2 <= len(t) <= 12:
                return t

    except Exception:
        pass

    return "AAPL"


# -----------------------------
# Main Router Agent
# -----------------------------

def run_finance_agent(user_query: str):
    q = user_query.lower().strip()

    # ✅ 1) Time-sensitive queries -> always web search
    # Tavily invoke uses {"query": "..."} per docs.
    # :contentReference[oaicite:4]{index=4}
    if any(word in q for word in TIME_SENSITIVE):
        return web_search(user_query)

    # ✅ 2) STOCK PRICE -> Finnhub symbol lookup -> Finnhub quote
    # Finnhub symbol search endpoint: /search?q=...
    # :contentReference[oaicite:5]{index=5}
    if ("stock price" in q) or ("share price" in q) or ("price of" in q):
        clean_q = clean_company_query(user_query)

        lookup = symbol_lookup(clean_q)

        # If symbol_lookup failed, fallback to web guessed symbol
        if isinstance(lookup, dict) and lookup.get("error"):
            symbol = fallback_symbol_from_web(user_query)
        else:
            results = lookup.get("result", []) if isinstance(lookup, dict) else []
            symbol = results[0].get("symbol") if results else None
            if not symbol:
                symbol = fallback_symbol_from_web(user_query)

        # Try Finnhub quote
        price_data = get_stock_price(symbol)

        # If Finnhub quote fails due to plan/market access (403 etc), fallback to web search
        # Permissions errors are commonly reported as 403 Forbidden.
        # :contentReference[oaicite:6]{index=6}
        if isinstance(price_data, dict) and price_data.get("error"):
            return web_search(f"{user_query} live stock price")

        return price_data

    # ✅ 3) COMPANY NEWS -> Finnhub company-news tool
    if "news" in q:
        symbol = extract_ticker(user_query)

        if not symbol:
            clean_q = clean_company_query(user_query)
            lookup = symbol_lookup(clean_q)

            if isinstance(lookup, dict) and not lookup.get("error"):
                results = lookup.get("result", [])
                if results:
                    symbol = results[0].get("symbol")

        symbol = symbol or "AAPL"
        return get_company_news(symbol)

    # ✅ 4) GOAL SAVING (e.g., "2 lakh in 10 months")
    if ("save" in q or "saving" in q) and ("month" in q or "months" in q):
        goal_amount = parse_indian_amount(q)
        months = extract_months(q)

        if goal_amount and months and months > 0:
            per_month = goal_amount / months
            return {
                "goal_amount": goal_amount,
                "months": months,
                "monthly_saving_required": round(per_month, 2),
                "tip": "Automate saving via SIP/RD so you don't miss months."
            }

    # ✅ 5) BUDGET / SALARY / INCOME
    if "salary" in q or "income" in q or "budget" in q:
        income = parse_indian_amount(q) or 50000

        # Simple 50/30/20 guideline
        fixed = round(income * 0.50)
        variable = round(income * 0.30)

        return budget_plan(income=income, fixed=fixed, variable=variable)

    # ✅ 6) Default -> Groq LLM (safe try/except)
    # Groq requires GROQ_API_KEY env var or passing key explicitly.
    # :contentReference[oaicite:7]{index=7}
    try:
        llm = get_llm()
        res = llm.invoke(user_query)
        return res.content
    except Exception as e:
        return {
            "error": "LLM failed (Groq)",
            "message": str(e),
            "fallback": "Ask a time-sensitive query (latest/current/news) so it uses web search."
        }
