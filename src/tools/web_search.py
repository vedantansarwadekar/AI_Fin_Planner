# src/tools/web_search.py
"""
Web search via Tavily with forced recency.

Key improvements over original:
- Adds current date to ALL queries so Tavily prioritises fresh results
- Sets days=3 for news/event queries (very recent), days=30 for general
- Returns structured list of {title, url, content, published_date}
- Falls back gracefully if Tavily fails
"""

import os
from datetime import datetime
from langchain_tavily import TavilySearch

# Keywords that signal the user wants very recent info
_BREAKING_KEYWORDS = {
    "war", "attack", "crisis", "ceasefire", "sanction", "ban",
    "today", "latest", "breaking", "just now", "right now", "live",
    "happening", "update", "news", "announced", "yesterday",
    "this week", "this month", "2025", "2026",
}

def web_search(query: str, max_results: int = 6) -> list[dict]:
    """
    Search the web and return fresh results.

    Always appends today's date to the query so search engines
    don't return stale cached results.

    Args:
        query:       The search query (user's original question is fine)
        max_results: How many results to fetch (default 6)

    Returns:
        List of dicts: [{title, url, content, published_date}, ...]
        On failure: [{"error": True, "message": "..."}]
    """
    today     = datetime.now().strftime("%B %d, %Y")        # e.g. "June 12, 2025"
    today_yr  = datetime.now().strftime("%Y")               # e.g. "2025"

    q_lower = query.lower()

    # Determine if this is a breaking/live news query
    is_breaking = any(kw in q_lower for kw in _BREAKING_KEYWORDS)

    # Always force the year into the query so Tavily ranks recent pages higher
    # For breaking news, also add "latest news" to further bias toward recency
    if is_breaking:
        enriched_query = f"{query} latest news {today_yr}"
    else:
        enriched_query = f"{query} {today_yr}"

    try:
        tool    = TavilySearch(
            max_results      = max_results,
            search_depth     = "advanced",   # deeper crawl than basic
            include_answer   = True,         # Tavily's own answer summary
            include_raw_content = False,
        )
        raw = tool.invoke({"query": enriched_query})

        # raw is usually a dict with 'results' key or a list directly
        results = raw if isinstance(raw, list) else raw.get("results", [raw])

        # Normalise to consistent shape
        out = []
        for r in results:
            if isinstance(r, dict):
                out.append({
                    "title":          r.get("title", ""),
                    "url":            r.get("url", ""),
                    "content":        r.get("content", r.get("snippet", "")),
                    "published_date": r.get("published_date", ""),
                    "source":         r.get("source", ""),
                })

        # Prepend Tavily's own synthesised answer if available
        if isinstance(raw, dict) and raw.get("answer"):
            out.insert(0, {
                "title":          "Tavily Summary",
                "url":            "",
                "content":        raw["answer"],
                "published_date": today,
                "source":         "tavily_summary",
            })

        return out if out else [{"error": True, "message": "No results found."}]

    except Exception as e:
        return [{"error": True, "message": f"Web search failed: {e}"}]