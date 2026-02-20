# src/agents/finance_agent.py

import re
from typing import Optional, List, Dict
from datetime import datetime

from src.llm import get_llm
from src.tools.web_search import web_search
from src.tools.market import get_stock_price
from src.tools.news import get_company_news
from src.tools.budget_calc import budget_plan
from src.tools.symbol_lookup import symbol_lookup


# =========================================================
# TIME-SENSITIVE KEYWORDS
# =========================================================

TIME_SENSITIVE = [
    "ipo",
    "upcoming",
    "repo rate",
    "interest rate",
    "latest",
    "today",
    "current",
    "deadline",
    "update",
    "announcement",
    "new rules",
    "happened on",
    "union budget",
    "news",
    "stocks",
    "stock",
    "announced"
]


# =========================================================
# HELPERS
# =========================================================

def extract_ticker(text: str) -> Optional[str]:
    tickers = re.findall(r"\b[A-Z]{2,10}\b", text.upper())
    blacklist = {
        "IPO", "INDIA", "NSE", "BSE", "STOCK", "SHARE",
        "PRICE", "RATE", "RBI", "NEWS"
    }
    tickers = [t for t in tickers if t not in blacklist]
    return tickers[-1] if tickers else None


def clean_company_query(user_query: str) -> str:
    q = user_query.lower().strip()
    q = re.sub(r"\b(stock|share|price|of|give|me|today|current|latest|pls|please)\b", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"[^a-zA-Z0-9\s&.-]", "", q).strip()
    return q if q else user_query.strip()


def parse_indian_amount(text: str) -> Optional[int]:
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
    return int(digits[0]) if digits else None


def extract_months(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*(month|months|mths)", text.lower())
    return int(match.group(1)) if match else None


def detect_date_query(query: str) -> Optional[str]:
    q = query.lower()
    pattern = r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?'
    match = re.search(pattern, q)

    if match:
        year = match.group(3) or datetime.now().year
        return f"news headlines {match.group(0)} {year}"

    return None


def build_conversation_context(chat_history: List[Dict]) -> str:
    if not chat_history:
        return ""

    context = "Conversation so far:\n"
    for msg in chat_history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        context += f"{role}: {msg['content']}\n"

    return context + "\n"


def format_with_llm(user_query: str, data, chat_history: List[Dict] = None) -> str:
    try:
        llm = get_llm()
        context = build_conversation_context(chat_history or [])

        prompt = f"""
{context}
User's question: "{user_query}"

Data retrieved:
{data}

Write a clear, well-structured, helpful answer.
- Be conversational
- Format numbers nicely
- Explain meaning
- If follow-up, use context
- Do NOT repeat raw JSON
"""

        res = llm.invoke(prompt)
        return res.content

    except Exception:
        return "I retrieved the data successfully, but formatting failed. Please try again."


# =========================================================
# MAIN ROUTER
# =========================================================

def run_finance_agent(user_query: str, chat_history: List[Dict] = None):

    if chat_history is None:
        chat_history = []

    q = user_query.lower().strip()

    # -----------------------------------------------------
    # 1️⃣ TIME-SENSITIVE → WEB SEARCH
    # -----------------------------------------------------
    if any(word in q for word in TIME_SENSITIVE):
        date_query = detect_date_query(user_query)
        if date_query:
            results = web_search(date_query)
        else:
            results = web_search(user_query)

        return format_with_llm(user_query, results, chat_history)

    # -----------------------------------------------------
    # 2️⃣ STOCK PRICE
    # -----------------------------------------------------
    if any(x in q for x in ["stock price", "share price", "price of"]):

        symbol = extract_ticker(user_query)

        if not symbol:
            clean_q = clean_company_query(user_query)
            lookup = symbol_lookup(clean_q)
            results = lookup.get("result", []) if isinstance(lookup, dict) else []
            symbol = results[0]["symbol"] if results else None

        if not symbol:
            search_results = web_search(f"{user_query} live stock price")
            return format_with_llm(user_query, search_results, chat_history)

        price_data = get_stock_price(symbol)

        if isinstance(price_data, dict) and price_data.get("current", 0) == 0:
            search_results = web_search(f"{user_query} live stock price")
            return format_with_llm(user_query, search_results, chat_history)

        return format_with_llm(user_query, price_data, chat_history)

    # -----------------------------------------------------
    # 3️⃣ NEWS
    # -----------------------------------------------------
    if "news" in q:

        date_query = detect_date_query(user_query)
        if date_query:
            results = web_search(date_query)
            return format_with_llm(user_query, results, chat_history)

        symbol = extract_ticker(user_query)

        if symbol:
            news_data = get_company_news(symbol)
            return format_with_llm(user_query, news_data, chat_history)

        results = web_search(user_query)
        return format_with_llm(user_query, results, chat_history)

    # -----------------------------------------------------
    # 4️⃣ SAVINGS GOAL
    # -----------------------------------------------------
    if ("save" in q or "saving" in q) and "month" in q:
        goal = parse_indian_amount(q)
        months = extract_months(q)

        if goal and months and months > 0:
            per_month = round(goal / months, 2)

            savings_data = {
                "goal_amount": goal,
                "months": months,
                "monthly_required": per_month,
                "tip": "Automate savings using SIP or recurring deposit."
            }

            return format_with_llm(user_query, savings_data, chat_history)

    # -----------------------------------------------------
    # 5️⃣ BUDGET
    # -----------------------------------------------------
    if any(x in q for x in ["salary", "income", "budget"]):
        income = parse_indian_amount(q) or 50000
        fixed = round(income * 0.5)
        variable = round(income * 0.3)

        budget_data = budget_plan(income=income, fixed=fixed, variable=variable)
        return format_with_llm(user_query, budget_data, chat_history)

    # -----------------------------------------------------
    # 6️⃣ DEFAULT → LLM WITH CONTEXT
    # -----------------------------------------------------
    try:
        llm = get_llm()
        context = build_conversation_context(chat_history)

        prompt = f"""
{context}
User: {user_query}

Give a detailed, structured, helpful response.
Use bullet points if useful.
"""

        res = llm.invoke(prompt)
        return res.content

    except Exception as e:
        return f"Something went wrong: {str(e)}"



