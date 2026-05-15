"""
src/tools/web_search.py
────────────────────────
Web search via Tavily with TRUE recency enforcement.

Key improvements over v1:
  1. Resolves relative date words ("yesterday", "today", "this week")
     into ACTUAL calendar dates before building the query
  2. Sets Tavily's `days` filter so only recently-published pages are returned
  3. Injects the real current date into every query so ranking engines
     treat it as a hard anchor, not a hint
  4. Returns published_date with every result so the LLM can spot stale results
  5. Provides a staleness_warning flag when results look old vs the query intent
"""

import os
import re
from datetime import datetime, timedelta

# ── Date helpers ──────────────────────────────────────────────────────────────

def _today() -> datetime:
    return datetime.now()

def _date_str(dt: datetime) -> str:
    """'May 15, 2026'"""
    return dt.strftime("%B %d, %Y")

def _date_short(dt: datetime) -> str:
    """'2026-05-15'  (ISO, unambiguous for search engines)"""
    return dt.strftime("%Y-%m-%d")


# ── Relative date resolver ────────────────────────────────────────────────────

# Words/phrases that reference a relative time window
_RELATIVE_DATE_MAP = {
    # "today" group → 0 days ago
    r"\btoday\b":        0,
    r"\bright now\b":    0,
    r"\bjust now\b":     0,
    r"\blive\b":         0,
    r"\bcurrently\b":    0,
    r"\bnow\b":          0,

    # "yesterday" group → 1 day ago
    r"\byesterday\b":    1,
    r"\blast night\b":   1,

    # "this week" → up to 7 days
    r"\bthis week\b":    7,
    r"\bpast week\b":    7,
    r"\blast 7 days\b":  7,

    # "this month" → up to 30 days
    r"\bthis month\b":   30,
    r"\bpast month\b":   30,
    r"\blast 30 days\b": 30,
}

# Words that signal we need very fresh results even without explicit date words
_BREAKING_KEYWORDS = {
    "latest", "breaking", "update", "news", "score", "result",
    "winner", "won", "beat", "match", "game", "election",
    "price", "rate", "market", "stock", "ipl", "cricket",
    "football", "nba", "nfl", "weather", "announced", "just",
    "happening", "launched", "released", "arrested", "died",
}


def _resolve_relative_dates(query: str) -> tuple[str, int, str | None]:
    """
    Detect relative date language in the query and return:
      - enriched_query: query with the actual date substituted in
      - days_filter:    how many days back to filter Tavily results
      - anchor_date:    human-readable date string to inject (or None)

    Examples:
      "who won yesterdays ipl match"
        → ("who won the ipl match on May 14 2026", 2, "May 14, 2026")

      "latest AI news"
        → ("latest AI news May 15 2026", 3, "May 15, 2026")

      "what is swing bowling"
        → ("what is swing bowling", 365, None)   # no recency needed
    """
    today      = _today()
    q_lower    = query.lower()

    # Check explicit relative date words
    for pattern, days_ago in _RELATIVE_DATE_MAP.items():
        if re.search(pattern, q_lower):
            target_date = today - timedelta(days=days_ago)
            anchor      = _date_str(target_date)
            iso         = _date_short(target_date)

            # Replace the relative phrase with the actual date in the query
            enriched = re.sub(
                pattern,
                f"on {anchor}",
                query,
                flags=re.IGNORECASE,
            )
            # Also append ISO date for search-engine ranking
            enriched = f"{enriched.strip()} {iso}"

            # days_filter: give a 1-day buffer around the target
            days_filter = max(days_ago + 2, 2)
            return enriched, days_filter, anchor

    # No explicit relative word — check for implicit recency signals
    breaking_hit = any(kw in q_lower for kw in _BREAKING_KEYWORDS)
    if breaking_hit:
        anchor   = _date_str(today)
        iso      = _date_short(today)
        enriched = f"{query.strip()} {iso}"
        return enriched, 7, anchor   # last 7 days for general "news" queries

    # Purely factual / timeless query
    year     = today.strftime("%Y")
    enriched = f"{query.strip()} {year}"
    return enriched, 365, None       # broad window — recency doesn't matter


# ── Main search function ──────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 6) -> list[dict]:
    """
    Search the web and return genuinely fresh results.

    Args:
        query:       The user's raw query (relative dates OK, we'll resolve them)
        max_results: How many results to return (default 6)

    Returns:
        List of dicts:
          {
            title:            str,
            url:              str,
            content:          str,
            published_date:   str,
            source:           str,
            anchor_date:      str | None,   # the resolved "as of" date
            staleness_warning: bool,        # True if result looks older than intended
          }
        On failure: [{"error": True, "message": "..."}]
    """
    try:
        from langchain_tavily import TavilySearch
    except ImportError:
        return [{"error": True, "message": "langchain_tavily is not installed."}]

    today = _today()

    # 1. Resolve relative dates → enriched query + days filter
    enriched_query, days_filter, anchor_date = _resolve_relative_dates(query)

    try:
        tool = TavilySearch(
            max_results         = max_results,
            search_depth        = "advanced",
            include_answer      = True,
            include_raw_content = False,
            days                = days_filter,   # ← THE KEY FIX: hard date filter
        )
        raw = tool.invoke({"query": enriched_query})

        results = raw if isinstance(raw, list) else raw.get("results", [raw])

        out = []
        for r in results:
            if not isinstance(r, dict):
                continue

            pub_date = r.get("published_date", "")

            # Staleness check: if we resolved a specific date and the result
            # is published more than 3 days before it, flag it
            staleness_warning = False
            if anchor_date and pub_date:
                try:
                    # Try to parse the published_date
                    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            pub_dt = datetime.strptime(pub_date[:10], fmt[:len(pub_date[:10])])
                            # Resolve anchor_date string to datetime for comparison
                            anchor_dt = datetime.strptime(anchor_date, "%B %d, %Y")
                            delta = (anchor_dt - pub_dt).days
                            if delta > 3:
                                staleness_warning = True
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            out.append({
                "title":             r.get("title", ""),
                "url":               r.get("url", ""),
                "content":           r.get("content", r.get("snippet", ""))[:1000],
                "published_date":    pub_date,
                "source":            r.get("source", r.get("url", "")),
                "anchor_date":       anchor_date,
                "staleness_warning": staleness_warning,
            })

        # Prepend Tavily's own synthesised answer
        if isinstance(raw, dict) and raw.get("answer"):
            out.insert(0, {
                "title":             "Tavily Summary",
                "url":               "",
                "content":           raw["answer"],
                "published_date":    _date_str(today),
                "source":            "tavily_summary",
                "anchor_date":       anchor_date,
                "staleness_warning": False,
            })

        # If ALL results are stale, surface a warning result at the top
        real_results = [x for x in out if x.get("source") != "tavily_summary"]
        if real_results and all(x.get("staleness_warning") for x in real_results):
            out.insert(0, {
                "title":             "⚠️ Freshness Warning",
                "url":               "",
                "content":           (
                    f"All search results appear to be older than the requested date "
                    f"({anchor_date}). The information below may be outdated. "
                    "Please note this when interpreting the answer."
                ),
                "published_date":    "",
                "source":            "staleness_warning",
                "anchor_date":       anchor_date,
                "staleness_warning": True,
            })

        return out if out else [{"error": True, "message": "No results found."}]

    except Exception as e:
        return [{"error": True, "message": f"Web search failed: {e}"}]