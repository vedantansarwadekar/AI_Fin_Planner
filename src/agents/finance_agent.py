# src/agents/finance_agent.py
"""
ATOM Finance Agent — v2

Improvements over v1:
  ─────────────────────────────────────────────────────────
  1. LLM-DRIVEN INTENT DETECTION
     Instead of brittle keyword matching, the LLM first classifies
     the query into one of 9 intents. Much more accurate routing.

  2. ALWAYS-FRESH WEB SEARCH
     web_search() now appends the current year + "latest" to all
     queries, fixing stale results for news/events/wars/policies.

  3. INDIAN STOCK SUPPORT
     market.py now uses Yahoo Finance (.NS/.BO) for Indian stocks
     so Finnhub's free-plan 403 errors no longer block Indian queries.

  4. NEW CALCULATORS
     SIP, EMI, lumpsum, income tax (new + old regime), FD, savings goal.

  5. STRONG INDIAN FINANCE SYSTEM PROMPT
     LLM always responds as an expert in Indian markets (NSE/BSE,
     RBI, SEBI, rupee, Indian tax law, mutual funds, etc.)

  Intents:
    stock_price   → get_stock_price()
    news          → get_company_news() or web_search()
    web_search    → web_search() (live events, policy, war, general news)
    sip           → sip_calculator()
    emi           → emi_calculator()
    tax           → income_tax_calculator()
    lumpsum       → lumpsum_calculator()
    fd            → fd_calculator()
    budget        → budget_plan() + savings_goal()
    general       → LLM directly (no tool needed)
"""

import re
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.llm import get_llm, get_llm_fast, get_llm_response, FAST_MODEL, SMART_MODEL
from src.tools.web_search import web_search
from src.tools.market import get_stock_price, get_company_news
from src.tools.calculators import (
    sip_calculator,
    lumpsum_calculator,
    emi_calculator,
    income_tax_calculator,
    fd_calculator,
    budget_plan,
    savings_goal,
)
from src.tools.symbol_lookup import symbol_lookup

logger = logging.getLogger("atom.finance")

# ── Indian Finance System Prompt ──────────────────────────────────────────────
_SYSTEM_PROMPT = """You are ATOM Finance — an expert AI financial advisor specialising in Indian personal finance and markets.

Your expertise covers:
• Indian stock markets: NSE, BSE, Nifty 50, Sensex, F&O
• Mutual funds: SIP, lumpsum, ELSS, debt, hybrid, index funds
• Indian banking: RBI policies, repo rate, FD/RD rates, savings accounts
• Tax: Income tax (old vs new regime), 80C, 80D, LTCG, STCG, TDS, ITR
• Insurance: Term life, health insurance (IRDAI guidelines)
• Loans & credit: Home loan, personal loan, car loan, EMI calculation
• Retirement: NPS, EPF, PPF, pension planning
• Indian economic context: inflation (CPI), GDP, SEBI regulations, Union Budget
• Global events that affect Indian markets (Fed rate decisions, oil prices, geopolitics)

Response style:
• Be specific and cite real numbers, rates, and dates when available
• Use ₹ symbol for Indian currency
• Format numbers in Indian style (lakhs, crores) when appropriate
• If data was retrieved live, mention "as of [date]"
• Be direct — give concrete advice, not just "consult a financial advisor"
• Keep responses well-structured with headers/bullets where useful
• Today's date: {today}
"""

# ── Intent classifier prompt ──────────────────────────────────────────────────
_INTENT_PROMPT = """Classify this finance query into exactly ONE intent.

Query: "{query}"

Intents:
- stock_price   : user wants current stock/share price of a company
- news          : user wants recent company-specific news or earnings
- web_search    : user wants live info (war, policy, RBI/SEBI update, IPO, budget, general current events)
- sip           : user wants SIP / mutual fund investment calculation
- emi           : user wants loan EMI calculation
- tax           : user wants income tax calculation or tax-saving advice
- lumpsum       : user wants one-time investment / lumpsum return calculation
- fd            : user wants fixed deposit / RD calculation
- budget        : user wants budget planning or monthly savings breakdown
- general       : anything else — explanation, comparison, advice, concept

Return ONLY a JSON object like this (no markdown, no explanation):
{{"intent": "stock_price", "entity": "Reliance", "numbers": []}}

Rules:
- entity: company name, person name, or main subject (empty string if none)
- numbers: list of numbers found in the query (e.g. [10000, 12, 8.5])
- Choose web_search for any question about current events, news, wars, government policy
"""


def _classify_intent(query: str) -> dict:
    """Use LLM to classify query intent. Falls back to web_search on failure."""
    try:
        raw = get_llm_response(
            prompt         = _INTENT_PROMPT.format(query=query),
            system_message = "You are a query classifier. Return only valid JSON.",
            temperature    = 0.0,
            model          = FAST_MODEL,   # cheap 8B model — just routing, not answering
        )
        # Strip markdown fences if any
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        result  = json.loads(cleaned)
        intent  = result.get("intent", "web_search")
        if intent not in {
            "stock_price","news","web_search","sip","emi",
            "tax","lumpsum","fd","budget","general"
        }:
            intent = "web_search"
        result["intent"] = intent
        return result
    except Exception as e:
        logger.warning(f"[Finance] Intent classification failed: {e} — defaulting to web_search")
        return {"intent": "web_search", "entity": "", "numbers": []}


# ── Number extractors ─────────────────────────────────────────────────────────

def _parse_numbers(text: str) -> list[float]:
    """Extract all numbers from text, handling Indian formats (lakh, crore)."""
    results = []
    # Handle lakh/crore first
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|crore|crores)", text.lower()):
        num  = float(match.group(1))
        unit = match.group(2)
        results.append(num * 100000 if "lakh" in unit else num * 10000000)
    # Plain numbers
    for match in re.finditer(r"\b(\d+(?:,\d+)*(?:\.\d+)?)\b", text):
        try:
            results.append(float(match.group(1).replace(",", "")))
        except ValueError:
            pass
    return results


def _extract_years(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*(?:year|yr|years|yrs)", text.lower())
    return int(match.group(1)) if match else None


def _extract_months(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*(?:month|months|mths|mo)", text.lower())
    if match:
        return int(match.group(1))
    # Convert years to months if needed
    y = _extract_years(text)
    return y * 12 if y else None


def _extract_rate(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(match.group(1)) if match else None


def _extract_regime(text: str) -> str:
    if "old" in text.lower():
        return "old"
    return "new"


# ── LLM response formatter ────────────────────────────────────────────────────

def _format_response(
    user_query:   str,
    tool_data:    Any,
    chat_history: List[Dict],
    extra_context: str = "",
) -> str:
    """Format tool output into a natural, well-structured response."""
    today     = datetime.now().strftime("%d %b %Y")
    system    = _SYSTEM_PROMPT.format(today=today)

    # Build conversation context (last 6 messages)
    conv = ""
    if chat_history:
        conv = "Recent conversation:\n"
        for msg in chat_history[-6:]:
            role = "User" if msg["role"] == "user" else "ATOM"
            conv += f"{role}: {msg['content']}\n"
        conv += "\n"

    prompt = f"""{conv}User's question: \"{user_query}\"

Data retrieved:
{json.dumps(tool_data, indent=2, default=str) if not isinstance(tool_data, str) else tool_data}

{extra_context}

Instructions:
- Give a clear, direct, helpful answer using the data above
- Use ₹ for currency, format numbers with commas
- Mention the source/date if data is live
- Do NOT repeat raw JSON — synthesise it into prose + bullets
- If the data shows an error, acknowledge it and give a helpful alternative
- Keep response concise but complete
"""
    try:
        return get_llm_response(prompt=prompt, system_message=system, temperature=0.3)
    except Exception as e:
        return f"I retrieved the data but couldn't format it. Raw result: {tool_data}"


# ── Main Router ───────────────────────────────────────────────────────────────

def run_finance_agent(user_query: str, chat_history: List[Dict] = None) -> str:
    """
    Main entry point for the Finance Agent.

    Flow:
      1. LLM classifies the intent
      2. Route to the right tool
      3. LLM formats the tool output into a natural response
    """
    if chat_history is None:
        chat_history = []

    today = datetime.now().strftime("%d %b %Y")
    logger.info(f"[Finance] Query: {user_query[:80]}")

    # ── Step 1: Classify intent ───────────────────────────────────────────────
    intent_data = _classify_intent(user_query)
    intent      = intent_data.get("intent", "web_search")
    entity      = intent_data.get("entity", "")
    numbers     = _parse_numbers(user_query)

    logger.info(f"[Finance] Intent: {intent} | Entity: {entity} | Numbers: {numbers}")

    # ── Step 2: Route to tool ────────────────────────────────────────────────

    # ── Stock Price ───────────────────────────────────────────────────────────
    if intent == "stock_price":
        target = entity or user_query
        data   = get_stock_price(target)

        if data.get("error"):
            # Fallback to web search for price
            search_q = f"{target} stock price today NSE BSE {today}"
            data = web_search(search_q)

        return _format_response(user_query, data, chat_history)

    # ── Company News ──────────────────────────────────────────────────────────
    elif intent == "news":
        target = entity or user_query
        data   = get_company_news(target)

        if not data or (isinstance(data, list) and data[0].get("error")):
            data = web_search(f"{target} news today {today}")

        return _format_response(user_query, data, chat_history)

    # ── Live Web Search (default for current events) ──────────────────────────
    elif intent == "web_search":
        data = web_search(user_query)
        extra = f"Note: Today is {today}. Prioritise the most recent information."
        return _format_response(user_query, data, chat_history, extra_context=extra)

    # ── SIP Calculator ────────────────────────────────────────────────────────
    elif intent == "sip":
        monthly  = numbers[0] if len(numbers) > 0 else None
        rate     = _extract_rate(user_query) or (numbers[1] if len(numbers) > 1 else 12.0)
        years    = _extract_years(user_query) or (int(numbers[2]) if len(numbers) > 2 else None)

        if not monthly or not years:
            return (
                "To calculate your SIP returns, I need:\n"
                "• **Monthly investment amount** (e.g. ₹5,000)\n"
                "• **Expected annual return** (e.g. 12%)\n"
                "• **Duration** (e.g. 10 years)\n\n"
                "Example: *'SIP of ₹5000 for 10 years at 12%'*"
            )

        data = sip_calculator(monthly, rate, years)
        return _format_response(user_query, data, chat_history)

    # ── EMI Calculator ────────────────────────────────────────────────────────
    elif intent == "emi":
        principal = numbers[0] if len(numbers) > 0 else None
        rate      = _extract_rate(user_query) or (numbers[1] if len(numbers) > 1 else None)
        months    = _extract_months(user_query) or (int(numbers[2]) if len(numbers) > 2 else None)

        if not principal or not rate or not months:
            return (
                "To calculate your EMI, I need:\n"
                "• **Loan amount** (e.g. ₹20 lakh)\n"
                "• **Interest rate** (e.g. 8.5%)\n"
                "• **Tenure** (e.g. 20 years or 240 months)\n\n"
                "Example: *'EMI for 20 lakh home loan at 8.5% for 20 years'*"
            )

        data = emi_calculator(principal, rate, months)
        return _format_response(user_query, data, chat_history)

    # ── Income Tax ────────────────────────────────────────────────────────────
    elif intent == "tax":
        income = numbers[0] if numbers else None
        regime = _extract_regime(user_query)

        if not income:
            return (
                "To calculate your income tax, tell me your **annual salary** "
                "and which **tax regime** you prefer.\n\n"
                "Example: *'Income tax on 12 lakh salary new regime'*\n"
                "Or: *'Tax on ₹8,00,000 old regime'*"
            )

        data = income_tax_calculator(income, regime)

        # Also compute the other regime for comparison
        other_regime = "old" if regime == "new" else "new"
        other_data   = income_tax_calculator(income, other_regime)
        extra = (
            f"For comparison, under the {other_regime} regime: "
            f"total tax = {other_data['total_tax']}, "
            f"effective rate = {other_data['effective_rate']}."
        )

        return _format_response(user_query, data, chat_history, extra_context=extra)

    # ── Lumpsum Investment ────────────────────────────────────────────────────
    elif intent == "lumpsum":
        principal = numbers[0] if len(numbers) > 0 else None
        rate      = _extract_rate(user_query) or (numbers[1] if len(numbers) > 1 else 12.0)
        years     = _extract_years(user_query) or (int(numbers[2]) if len(numbers) > 2 else None)

        if not principal or not years:
            return (
                "To calculate lumpsum returns, I need:\n"
                "• **Investment amount** (e.g. ₹1 lakh)\n"
                "• **Expected annual return** (e.g. 12%)\n"
                "• **Duration** (e.g. 5 years)\n\n"
                "Example: *'If I invest 1 lakh lumpsum for 5 years at 12%'*"
            )

        data = lumpsum_calculator(principal, rate, years)
        return _format_response(user_query, data, chat_history)

    # ── FD Calculator ─────────────────────────────────────────────────────────
    elif intent == "fd":
        principal = numbers[0] if len(numbers) > 0 else None
        rate      = _extract_rate(user_query) or (numbers[1] if len(numbers) > 1 else 7.0)
        years     = _extract_years(user_query) or 1

        if not principal:
            return (
                "To calculate FD maturity, I need:\n"
                "• **Deposit amount** (e.g. ₹1 lakh)\n"
                "• **Interest rate** (e.g. 7.5%)\n"
                "• **Duration** (e.g. 2 years)\n\n"
                "Example: *'FD of 1 lakh at 7.5% for 2 years'*"
            )

        data = fd_calculator(principal, rate, years)
        return _format_response(user_query, data, chat_history)

    # ── Budget Planning ───────────────────────────────────────────────────────
    elif intent == "budget":
        income = numbers[0] if numbers else None

        if not income:
            return (
                "Tell me your **monthly salary or income** and I'll create a budget plan.\n\n"
                "Example: *'Budget plan for ₹60,000 salary'*"
            )

        budget_data = budget_plan(income)

        # Check if it's also a savings goal query
        if "save" in user_query.lower() or "saving" in user_query.lower():
            months = _extract_months(user_query)
            target = numbers[1] if len(numbers) > 1 else None
            if target and months:
                goal_data = savings_goal(target, months)
                return _format_response(
                    user_query,
                    {"budget": budget_data, "savings_goal": goal_data},
                    chat_history
                )

        return _format_response(user_query, budget_data, chat_history)

    # ── General Finance Question ──────────────────────────────────────────────
    else:  # intent == "general"
        today_str = datetime.now().strftime("%d %b %Y")
        system    = _SYSTEM_PROMPT.format(today=today_str)

        # Build conversation context
        conv = ""
        if chat_history:
            conv = "Recent conversation:\n"
            for msg in chat_history[-6:]:
                role = "User" if msg["role"] == "user" else "ATOM"
                conv += f"{role}: {msg['content']}\n"
            conv += "\n"

        prompt = f"""{conv}User: {user_query}

Give a clear, well-structured, expert answer about Indian finance.
Use ₹ for currency. Cite real rates, rules, and examples where helpful.
"""
        try:
            return get_llm_response(
                prompt         = prompt,
                system_message = system,
                temperature    = 0.4,
                model          = SMART_MODEL,  # full 70B for actual answers
            )
        except Exception as e:
            return f"Something went wrong: {str(e)}"