"""
src/agents/workspace_agent.py
─────────────────────────────
ATOM AI OS — General-purpose intelligent workspace agent.
"""

import logging
from datetime import datetime, timedelta
from src.tools.web_search import web_search
from src.llm import get_llm_response, get_llm_response_with_history, FAST_MODEL, SMART_MODEL

logger = logging.getLogger("atom.workspace_agent")


def _today_str() -> str:
    return datetime.now().strftime("%B %d, %Y")   # "May 15, 2026"


_SEARCH_TRIGGERS = {
    "latest", "current", "today", "now", "live", "breaking", "recent",
    "this week", "this month", "2025", "2026", "yesterday", "just",
    "happening", "update", "news", "announced",
    "price", "score", "result", "standing", "weather", "rate",
    "stock", "market", "vs", "compare", "best", "top", "review",
    "who is", "what is the", "how much", "where is",
    "ipl", "cricket", "football", "nba", "match", "election",
    "nvidia", "openai", "apple", "google", "tesla",
    "won", "winner", "beat", "defeated",
}

_DIRECT_LLM_SIGNALS = {
    "explain", "how does", "define", "write", "code",
    "fix", "error", "help me", "summarize", "give me", "create",
    "draft", "suggest", "improve", "translate", "make", "generate",
    "write a", "example of", "difference between",
}

_SYSTEM_PROMPT = """You are ATOM AI OS — a brilliant, fast, and honest general-purpose AI assistant.

Today's date is: {today}

Your personality:
- Clear, direct, confident, and warm
- You use markdown formatting: headers, bold, bullet points, code blocks where helpful
- You cite sources inline when using web search results
- For code, always use proper markdown code blocks with language tags

Rules:
- Never say "As an AI..." or "I don't have real-time data"
- If web results are provided, use them confidently
- Be concise but complete
- If a question is ambiguous, pick the most reasonable interpretation and answer it
"""

_SEARCH_SYNTHESIS_PROMPT = """You are ATOM AI OS. Today's date is {today}.

The user asked: "{query}"
{anchor_note}

CRITICAL FRESHNESS RULES:
- Today is {today}. Any result published before {cutoff} should be treated as potentially stale.
- If a result's published_date is more than 3 days before the intended date, note that explicitly.
- If results contradict each other, prefer the more recently published one.
- If ALL results appear stale (old dates), say so clearly and caveat your answer.
- NEVER present old results as if they are current without flagging the date.

Formatting rules:
- Lead with the most important, most recent information
- Use inline source attribution: "According to [source name] (published: [date])..."
- Use markdown (headers, bullets, bold) appropriately

Web Search Results:
{search_results}

Write a comprehensive, date-aware answer:"""


def classify_query(query: str) -> str:
    q_lower = query.lower().strip()
    direct_score = sum(1 for kw in _DIRECT_LLM_SIGNALS if kw in q_lower)
    search_score = sum(1 for kw in _SEARCH_TRIGGERS   if kw in q_lower)

    if direct_score >= 2 and search_score == 0:
        return "direct"
    if search_score >= 1:
        return "search"

    classification_prompt = (
        f'You are a query router. Today is {_today_str()}.\n'
        'Reply with ONLY one word: "search" or "direct"\n\n'
        'Rules:\n'
        '- "search" if: current events, scores, prices, news, recent releases, real-world facts that change\n'
        '- "direct" if: coding help, writing, explanations, definitions, how-to, creative, math, stable knowledge\n\n'
        f'Query: "{query}"\n\nAnswer:'
    )

    result = get_llm_response(prompt=classification_prompt, temperature=0.0, model=FAST_MODEL).strip().lower()
    return "search" if "search" in result else "direct"


def _format_search_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        if r.get("error"):
            continue
        title   = r.get("title", "")
        url     = r.get("url", "")
        content = r.get("content", "")[:900]
        date    = r.get("published_date", "unknown date")
        source  = r.get("source", url)
        stale   = r.get("staleness_warning", False)

        stale_tag = " ⚠️ [POSSIBLY STALE]" if stale else ""
        lines.append(
            f"[{i}] {title}{stale_tag}\n"
            f"Published: {date} | Source: {source}\n"
            f"{content}"
        )
    return "\n\n".join(lines) if lines else "No useful results found."


def run_workspace_agent(query: str, chat_history: list[dict] | None = None) -> dict:
    chat_history = chat_history or []
    today        = _today_str()

    mode = classify_query(query)
    logger.info(f"[WorkspaceAgent] mode={mode} | query='{query[:60]}'")

    sources = []

    if mode == "search":
        raw_results = web_search(query, max_results=6)
        sources     = [r for r in raw_results if not r.get("error")]

        if sources:
            search_block = _format_search_results(sources)
            anchor_date  = sources[0].get("anchor_date") if sources else None

            if anchor_date:
                anchor_note = (
                    f"Note: The user's query refers to events around {anchor_date}. "
                    "Only use results relevant to that date."
                )
                try:
                    anchor_dt = datetime.strptime(anchor_date, "%B %d, %Y")
                    cutoff    = (anchor_dt - timedelta(days=3)).strftime("%B %d, %Y")
                except Exception:
                    cutoff = anchor_date
            else:
                anchor_note = ""
                cutoff      = today

            synthesis_prompt = _SEARCH_SYNTHESIS_PROMPT.format(
                today          = today,
                query          = query,
                anchor_note    = anchor_note,
                cutoff         = cutoff,
                search_results = search_block,
            )

            answer = get_llm_response_with_history(
                prompt         = synthesis_prompt,
                chat_history   = chat_history,
                system_message = _SYSTEM_PROMPT.format(today=today),
                temperature    = 0.2,
                model          = SMART_MODEL,
            )
        else:
            logger.warning("[WorkspaceAgent] Search returned no results, falling back to direct")
            mode = "direct"

    if mode == "direct" or not sources:
        answer = get_llm_response_with_history(
            prompt         = query,
            chat_history   = chat_history,
            system_message = _SYSTEM_PROMPT.format(today=today),
            temperature    = 0.4,
            model          = SMART_MODEL,
        )

    return {"answer": answer, "mode": mode, "sources": sources}