"""
src/agents/router_agent.py
───────────────────────────
ATOM Auto-Mode Router

Responsibilities:
  1. classify_query()      — 5-way agent classifier with confidence score
  2. resolve_upload_intent() — determines which agent should handle a file
                               (always deferred to user via UI, but we pre-suggest)
  3. AGENT_META             — display names, descriptions, icons for UI

Flow in Auto Mode:
  User types query
    → classify_query() → (agent_key, confidence, reason)
    → App shows: "I think this belongs in [Agent] — [reason]. Shall I proceed?"
    → User confirms → run that agent
    → User declines → show alternative agents → user picks → run that agent
"""

import logging
from src.llm import get_llm_response, FAST_MODEL, SMART_MODEL

logger = logging.getLogger("atom.router")

# ── Agent registry ─────────────────────────────────────────────────────────────
# Used by both the router and the UI to render agent options consistently.

AGENT_META = {
    "ai_os": {
        "label":       "⚛️ ATOM AI OS",
        "description": "General questions, web search, coding, writing, research",
        "icon":        "⚛️",
        "radio_label": "⚛️ ATOM AI OS",
    },
    "finance": {
        "label":       "Finance Planner",
        "description": "Budgeting, investing, SIP, EMI, tax, mutual funds, insurance",
        "icon":        "💸",
        "radio_label": "Finance Planner",
    },
    "stock_rag": {
        "label":       "Stock Market RAG",
        "description": "SEBI/RBI regulations, circulars, IPO rules, NSE/BSE policy docs",
        "icon":        "📈",
        "radio_label": "Stock Market RAG",
    },
    "data_analyst": {
        "label":       "Data Analyst",
        "description": "Analyse uploaded CSV/Excel, charts, trends, data questions",
        "icon":        "📊",
        "radio_label": "Data Analyst",
    },
    "my_documents": {
        "label":       "My Documents",
        "description": "Search and ask questions about your privately uploaded documents",
        "icon":        "📂",
        "radio_label": "My Documents",
    },
}

# ── Keyword signals per agent ──────────────────────────────────────────────────

_FINANCE_KW = {
    "budget", "invest", "investment", "sip", "emi", "tax", "mutual fund",
    "portfolio", "savings", "loan", "insurance", "retirement", "fd", "ppf",
    "nps", "equity", "debt", "gold", "real estate", "expense", "income",
    "salary", "wealth", "financial plan", "credit card", "interest rate",
    "inflation", "returns", "dividend", "net worth", "asset", "liability",
    "pension", "ulip", "elss", "itr", "80c", "capital gain",
}

_STOCK_RAG_KW = {
    "sebi", "rbi", "regulation", "circular", "guideline", "policy",
    "nse", "bse", "ipo rules", "listing", "disclosure", "compliance",
    "prospectus", "offeror", "insider trading", "takeover", "merger",
    "acquisition", "demat", "broker", "depository", "nsdl", "cdsl",
    "stock exchange", "market regulation", "securities law",
}

_DATA_ANALYST_KW = {
    "dataset", "csv", "excel", "spreadsheet", "dataframe", "column",
    "row", "chart", "plot", "graph", "trend", "correlation", "regression",
    "analyse", "analyze", "visualize", "visualise", "histogram", "bar chart",
    "pie chart", "scatter", "aggregate", "group by", "pivot", "summary stats",
    "uploaded file", "my data", "the data",
}

_MY_DOCS_KW = {
    "my document", "my pdf", "uploaded document", "my file", "the document",
    "the pdf", "the report", "according to", "in the document", "in my file",
    "what does it say", "find in", "search my", "my upload",
}

# Everything else → AI OS


# ── Classifier ─────────────────────────────────────────────────────────────────

def classify_query(
    query:          str,
    data_loaded:    bool = False,
    has_user_docs:  bool = False,
    rag_ready:      bool = False,
) -> dict:
    """
    Classify a user query into the best agent.

    Args:
        query:         The user's raw message
        data_loaded:   True if a CSV/Excel is already loaded in Data Analyst
        has_user_docs: True if the user has documents in My Documents
        rag_ready:     True if RAG index is built

    Returns:
        {
            "agent":      str,   # key from AGENT_META
            "confidence": str,   # "high" | "medium" | "low"
            "reason":     str,   # one short sentence explaining the choice
            "alternates": list,  # other plausible agent keys, ranked
        }
    """
    q = query.lower().strip()

    # ── Step 1: keyword scoring ────────────────────────────────────────────
    scores = {
        "finance":      sum(1 for kw in _FINANCE_KW      if kw in q),
        "stock_rag":    sum(1 for kw in _STOCK_RAG_KW    if kw in q),
        "data_analyst": sum(1 for kw in _DATA_ANALYST_KW if kw in q),
        "my_documents": sum(1 for kw in _MY_DOCS_KW      if kw in q),
        "ai_os":        0,
    }

    # ── Step 2: context signals ────────────────────────────────────────────
    # Boost agents that are actually available
    if not data_loaded:   scores["data_analyst"] = max(scores["data_analyst"] - 2, 0)
    if not has_user_docs: scores["my_documents"] = max(scores["my_documents"] - 2, 0)
    if not rag_ready:     scores["stock_rag"]    = max(scores["stock_rag"]    - 1, 0)

    top_score  = max(scores.values())
    top_agents = [k for k, v in scores.items() if v == top_score]

    # ── Step 3: clear winner → high confidence ─────────────────────────────
    if top_score >= 2 and len(top_agents) == 1:
        winner = top_agents[0]
        alternates = _rank_alternates(scores, winner)
        return {
            "agent":      winner,
            "confidence": "high",
            "reason":     _reason(winner, query),
            "alternates": alternates,
        }

    # ── Step 4: ambiguous or no signal → ask fast LLM ─────────────────────
    available = []
    if data_loaded:    available.append("data_analyst — analyse uploaded CSV/Excel data")
    if has_user_docs:  available.append("my_documents — search user's private uploaded docs")
    if rag_ready:      available.append("stock_rag — SEBI/RBI regulatory document search")
    available.append("finance — financial planning, investing, tax, budgeting")
    available.append("ai_os — general knowledge, web search, coding, writing, research")

    prompt = (
        f"You are an agent router for ATOM, a multi-agent AI platform.\n"
        f"Available agents:\n"
        + "\n".join(f"  - {a}" for a in available)
        + f"\n\nUser query: \"{query}\"\n\n"
        "Reply with ONLY a JSON object like:\n"
        '{"agent": "finance", "confidence": "medium", "reason": "one sentence"}\n\n'
        "agent must be one of: ai_os, finance, stock_rag, data_analyst, my_documents\n"
        "confidence: high / medium / low\n"
        "reason: one short sentence (max 12 words) explaining why"
    )

    try:
        import json, re
        raw = get_llm_response(prompt=prompt, temperature=0.0, model=FAST_MODEL)
        # Extract JSON from response
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            agent  = result.get("agent", "ai_os")
            if agent not in AGENT_META:
                agent = "ai_os"
            alternates = _rank_alternates(scores, agent)
            return {
                "agent":      agent,
                "confidence": result.get("confidence", "medium"),
                "reason":     result.get("reason", _reason(agent, query)),
                "alternates": alternates,
            }
    except Exception as e:
        logger.warning(f"[Router] LLM classification failed: {e}")

    # ── Step 5: hard fallback → AI OS ─────────────────────────────────────
    return {
        "agent":      "ai_os",
        "confidence": "low",
        "reason":     "No strong signal found — defaulting to general AI.",
        "alternates": ["finance", "stock_rag", "data_analyst", "my_documents"],
    }


def _rank_alternates(scores: dict, winner: str) -> list:
    """Return agent keys ranked by score, excluding the winner."""
    ranked = sorted(
        [k for k in scores if k != winner],
        key=lambda k: scores[k],
        reverse=True,
    )
    return ranked


def _reason(agent: str, query: str) -> str:
    """Generate a short human-readable reason for the routing decision."""
    reasons = {
        "finance":      "Your query looks like a personal finance question.",
        "stock_rag":    "This seems to be about market regulations or SEBI/RBI policy.",
        "data_analyst": "You have a dataset loaded — this looks like a data question.",
        "my_documents": "This looks like a question about your uploaded documents.",
        "ai_os":        "This is a general question best handled by web search and reasoning.",
    }
    return reasons.get(agent, "Best match based on your query.")


# ── Upload intent helper ───────────────────────────────────────────────────────

def suggest_upload_agent(filename: str, file_type: str) -> str:
    """
    Suggest which agent should handle an uploaded file.
    Always show the picker to the user — this just pre-selects the default.

    Returns agent key: "data_analyst" | "my_documents"
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"csv", "xlsx", "xls"}:
        return "data_analyst"
    return "my_documents"


# ── Confirmation message builder ───────────────────────────────────────────────

def build_routing_message(agent: str, confidence: str, reason: str) -> str:
    """
    Build the conversational routing confirmation message shown in chat
    before running the agent.
    """
    meta = AGENT_META.get(agent, AGENT_META["ai_os"])
    icon  = meta["icon"]
    label = meta["label"]

    conf_qualifier = {
        "high":   "I'm confident this belongs in",
        "medium": "I think this is best handled by",
        "low":    "I'm not entirely sure, but I'll try",
    }.get(confidence, "I'll route this to")

    return (
        f"{icon} **{conf_qualifier} {label}.**\n\n"
        f"_{reason}_\n\n"
        f"Shall I go ahead? Hit **✅ Yes** to proceed or **🔄 Switch agent** to choose a different one."
    )