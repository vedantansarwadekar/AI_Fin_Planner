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


def detect_and_format_date_query(query: str) -> Optional[str]:
    """
    Detects if query is asking for news from a specific date and reformats it
    for better web search results.
    
    Examples:
    - "news of 1 jan 2026" -> "news headlines January 1 2026"
    - "give me news from 15th january" -> "news headlines January 15 2026"
    - "what happened on 5 jan" -> "what happened January 5 2026"
    """
    q_lower = query.lower()
    
    # Common date patterns
    date_patterns = [
        r'(\d{1,2})\s*(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?',
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{1,2})\s*(st|nd|rd|th)?\s*(\d{4})?',
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, q_lower)
        if match:
            # If year not provided, assume current year
            current_year = datetime.now().year
            
            # Reformat the query to be more search-friendly
            if "what happened" in q_lower:
                return f"what happened on {match.group(0)} news headlines"
            else:
                return f"news headlines {match.group(0)} {current_year if len(match.groups()) < 4 else ''}"
    
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


def build_conversation_context(chat_history: List[Dict]) -> str:
    """
    Converts chat history into a readable context string for the LLM.
    """
    if not chat_history:
        return ""
    
    context = "Previous conversation:\n"
    for msg in chat_history[-6:]:  # Only keep last 6 messages to avoid token limits
        role = "User" if msg["role"] == "user" else "Assistant"
        context += f"{role}: {msg['content']}\n"
    
    return context + "\n"


def format_with_llm(user_query: str, data, chat_history: List[Dict] = None) -> str:
    """
    Takes raw data (JSON, dict, or any structured format) and asks LLM 
    to format it conversationally based on the user's original question.
    Now includes conversation context for better responses.
    """
    try:
        llm = get_llm()
        
        # Build context from chat history
        context = build_conversation_context(chat_history or [])
        
        prompt = f"""{context}User's current question: "{user_query}"

I retrieved this data: {data}

Please provide a clear, conversational response to the user's question using this data. 
If the user is asking a follow-up question, use the conversation context to understand what they're referring to.
Format numbers nicely, explain what the data means, and be helpful and friendly.
Do not just repeat the JSON - make it readable and useful for a human."""

        res = llm.invoke(prompt)
        return res.content
    except Exception as e:
        # If LLM fails, return the raw data as fallback
        return f"Here's what I found: {data}\n\n(Note: Formatting failed - {str(e)})"


# -----------------------------
# Main Router Agent
# -----------------------------

def run_finance_agent(user_query: str, chat_history: List[Dict] = None):
    """
    Main agent that routes queries to appropriate tools.
    
    Args:
        user_query: The current user question
        chat_history: List of previous messages [{"role": "user/assistant", "content": "..."}]
    """
    if chat_history is None:
        chat_history = []
    
    q = user_query.lower().strip()

    # ✅ 1) Time-sensitive queries -> web search -> format with LLM
    if any(word in q for word in TIME_SENSITIVE):
        search_results = web_search(user_query)
        return format_with_llm(user_query, search_results, chat_history)

    # ✅ 2) STOCK PRICE -> get data -> format with LLM
    if ("stock price" in q) or ("share price" in q) or ("price of" in q):
        clean_q = clean_company_query(user_query)

        # Try direct ticker first
        direct_ticker = extract_ticker(user_query)
        
        if direct_ticker:
            symbol = direct_ticker
        else:
            # Try Finnhub symbol lookup
            lookup = symbol_lookup(clean_q)
            
            if isinstance(lookup, dict) and lookup.get("error"):
                symbol = fallback_symbol_from_web(user_query)
            else:
                results = lookup.get("result", []) if isinstance(lookup, dict) else []
                if results:
                    symbol = results[0].get("symbol")
                else:
                    symbol = fallback_symbol_from_web(user_query)

        # Get price from Finnhub
        price_data = get_stock_price(symbol)

        # If Finnhub returns error or zeros, fallback to web search
        if isinstance(price_data, dict):
            if price_data.get("error") or price_data.get("current", 0) == 0:
                search_results = web_search(f"{user_query} live stock price current")
                return format_with_llm(user_query, search_results, chat_history)

        # Format price data conversationally
        return format_with_llm(user_query, price_data, chat_history)

    # ✅ 3) COMPANY NEWS (IMPROVED - handles company-specific, general, and date-based news)
    if "news" in q:
        # First check if this is a date-based news query
        formatted_date_query = detect_and_format_date_query(user_query)
        if formatted_date_query:
            # This is a date-specific news request, use web search with better formatting
            search_results = web_search(formatted_date_query)
            return format_with_llm(user_query, search_results, chat_history)
        
        # Check if user mentioned a specific company/ticker
        symbol = extract_ticker(user_query)
        
        if not symbol:
            clean_q = clean_company_query(user_query)
            lookup = symbol_lookup(clean_q)
            
            if isinstance(lookup, dict) and not lookup.get("error"):
                results = lookup.get("result", [])
                if results:
                    symbol = results[0].get("symbol")
        
        # If we found a company symbol, get company-specific news
        if symbol:
            news_data = get_company_news(symbol)
            # Check if news data is empty or has errors
            if isinstance(news_data, dict) and (news_data.get("error") or not news_data.get("data")):
                # Fallback to web search if Finnhub fails
                search_results = web_search(user_query)
                return format_with_llm(user_query, search_results, chat_history)
            return format_with_llm(user_query, news_data, chat_history)
        else:
            # No company found - this is a general news query, use web search
            search_results = web_search(user_query)
            return format_with_llm(user_query, search_results, chat_history)

    # ✅ 4) GOAL SAVING -> calculate -> format with LLM
    if ("save" in q or "saving" in q) and ("month" in q or "months" in q):
        goal_amount = parse_indian_amount(q)
        months = extract_months(q)

        if goal_amount and months and months > 0:
            per_month = goal_amount / months
            savings_data = {
                "goal_amount": goal_amount,
                "months": months,
                "monthly_saving_required": round(per_month, 2),
                "tip": "Automate saving via SIP/RD so you don't miss months."
            }
            return format_with_llm(user_query, savings_data, chat_history)

    # ✅ 5) BUDGET / SALARY / INCOME -> calculate -> format with LLM
    if "salary" in q or "income" in q or "budget" in q:
        income = parse_indian_amount(q) or 50000

        # Simple 50/30/20 guideline
        fixed = round(income * 0.50)
        variable = round(income * 0.30)

        budget_data = budget_plan(income=income, fixed=fixed, variable=variable)
        return format_with_llm(user_query, budget_data, chat_history)

    # ✅ 6) Default -> Groq LLM with conversation context
    try:
        llm = get_llm()
        
        # Build conversation context
        context = build_conversation_context(chat_history)
        
        # Add context to the query
        full_prompt = f"{context}User's current question: {user_query}\n\nPlease provide a helpful response based on the conversation context."
        
        res = llm.invoke(full_prompt)
        return res.content
    except Exception as e:
        return {
            "error": "LLM failed (Groq)",
            "message": str(e),
            "fallback": "Ask a time-sensitive query (latest/current/news) so it uses web search."
        }
    