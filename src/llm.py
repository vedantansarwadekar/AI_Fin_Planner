"""
src/llm.py
──────────
LLM utilities for all ATOM agents using LangChain + Groq.

Two-model strategy to conserve free-plan tokens:
  FAST model  (llama-3.1-8b-instant)     → intent classification, simple routing,
                                            calculator formatting — cheap & quick
  SMART model (llama-3.3-70b-versatile)  → actual answers, web search formatting,
                                            complex finance explanations

Token warning threshold: 100,000 per 60s (raised from 40k).
Groq free plan actual limits (as of 2025):
  llama-3.3-70b-versatile : 6,000 TPM  / 500 RPM
  llama-3.1-8b-instant    : 20,000 TPM / 30 RPM
  (TPM = tokens per minute, RPM = requests per minute)
"""

import time
import logging

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from src.config import GROQ_API_KEY

# ── Model names ──────────────────────────────────────────────────────────────
# Use these constants everywhere instead of hardcoding model strings
FAST_MODEL  = "llama-3.1-8b-instant"      # cheap: intent classify, simple tasks
SMART_MODEL = "llama-3.3-70b-versatile"   # powerful: answers, formatting, analysis

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atom.llm")

# ── Retry config ──────────────────────────────────────────────────────────────
MAX_RETRIES = 4       # total attempts before giving up
BASE_DELAY  = 2.0     # seconds — doubles each retry (2 → 4 → 8 → 16)
MAX_DELAY   = 60.0    # cap so we never wait more than a minute

# ── Token-usage tracker (rolling 60-second window, in-memory) ─────────────────
class _UsageTracker:
    WARN_TOKENS_PER_MIN = 100_000  # free plan Groq limit is ~14,400 TPM per model

    def __init__(self):
        self._window: list[tuple[float, int]] = []  # (timestamp, token_count)

    def record(self, tokens: int):
        now = time.time()
        self._window.append((now, tokens))
        self._window = [(t, n) for t, n in self._window if now - t < 60]
        total = sum(n for _, n in self._window)
        if total > self.WARN_TOKENS_PER_MIN:
            logger.warning(
                f"[LLM] High usage: ~{total:,} tokens in last 60s. "
                "Consider reducing request frequency."
            )

    def tokens_last_minute(self) -> int:
        now = time.time()
        return sum(n for t, n in self._window if now - t < 60)


_usage = _UsageTracker()


# ── Retry helper ──────────────────────────────────────────────────────────────
def _invoke_with_retry(llm: ChatGroq, messages: list, attempt_label: str = "") -> str:
    """
    Invoke a LangChain ChatGroq instance with automatic retry.

    Handles:
      - groq.RateLimitError    (429) → exponential backoff, reads Retry-After header
      - groq.APIStatusError    (5xx) → exponential backoff
      - groq.APIConnectionError      → linear backoff, up to MAX_RETRIES
      - Any other Exception          → returned as a human-readable error string
                                       (so the app never crashes hard)
    """
    # Import groq exceptions here so they're only required when actually called.
    # This keeps the module importable even before 'groq' is installed.
    try:
        import groq as _groq
        RateLimitError    = _groq.RateLimitError
        APIStatusError    = _groq.APIStatusError
        APIConnectionError = _groq.APIConnectionError
    except ImportError:
        # Fallback: catch everything as a generic Exception
        RateLimitError = APIStatusError = APIConnectionError = Exception

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"[LLM] {attempt_label} attempt {attempt}/{MAX_RETRIES}")
            response = llm.invoke(messages)

            # Estimate tokens from content length (LangChain/Groq doesn't always
            # expose usage in the same way as raw SDK — use response_metadata if available)
            token_count = 0
            if hasattr(response, "response_metadata"):
                meta = response.response_metadata or {}
                usage = meta.get("token_usage") or meta.get("usage") or {}
                token_count = (
                    usage.get("total_tokens")
                    or usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                    or len(response.content) // 4   # rough fallback: ~4 chars/token
                )
            else:
                token_count = len(response.content) // 4

            _usage.record(token_count)
            logger.info(f"[LLM] OK | ~{token_count} tokens | "
                        f"last-60s total: {_usage.tokens_last_minute():,}")

            return response.content

        except RateLimitError as e:
            # Try to read Retry-After from the response headers
            wait = _parse_retry_after(e)
            if wait is None:
                wait = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)

            if attempt < MAX_RETRIES:
                logger.warning(
                    f"[LLM] Rate limited (attempt {attempt}). "
                    f"Waiting {wait:.1f}s…"
                )
                time.sleep(wait)
            else:
                msg = (
                    f"Rate limit hit after {MAX_RETRIES} attempts. "
                    "Please wait a moment and try again."
                )
                logger.error(f"[LLM] {msg}")
                return f"⚠️ {msg}"

        except APIStatusError as e:
            status = getattr(e, "status_code", 0)
            if status >= 500:
                wait = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"[LLM] Server error {status} (attempt {attempt}). "
                        f"Waiting {wait:.1f}s…"
                    )
                    time.sleep(wait)
                else:
                    msg = f"Groq server error ({status}) after {MAX_RETRIES} attempts."
                    logger.error(f"[LLM] {msg}")
                    return f"⚠️ {msg}"
            else:
                # 4xx that isn't rate-limit — don't retry, surface immediately
                msg = f"API error {status}: {getattr(e, 'message', str(e))}"
                logger.error(f"[LLM] {msg}")
                return f"⚠️ {msg}"

        except APIConnectionError as e:
            wait = min(BASE_DELAY * attempt, MAX_DELAY)
            if attempt < MAX_RETRIES:
                logger.warning(
                    f"[LLM] Connection error (attempt {attempt}). "
                    f"Retrying in {wait:.1f}s…"
                )
                time.sleep(wait)
            else:
                msg = (
                    f"Could not connect to Groq API after {MAX_RETRIES} attempts. "
                    "Check your internet connection."
                )
                logger.error(f"[LLM] {msg}")
                return f"⚠️ {msg}"

        except Exception as e:
            # Unexpected error — don't retry, surface it cleanly
            msg = f"Unexpected LLM error: {str(e)}"
            logger.exception(f"[LLM] {msg}")
            return f"⚠️ {msg}"

    return "⚠️ LLM request failed after all retries."


def _parse_retry_after(error) -> float | None:
    """Extract Retry-After seconds from error headers if present."""
    try:
        headers = error.response.headers
        val = (
            headers.get("retry-after")
            or headers.get("x-ratelimit-reset-requests")
            or headers.get("x-ratelimit-reset-tokens")
        )
        return float(val) if val else None
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_llm(temperature: float = 0.2, model: str = None) -> ChatGroq:
    """
    Get a configured LangChain ChatGroq instance.

    Args:
        temperature: Response creativity (0–1)
        model:       Groq model name

    Returns:
        ChatGroq instance

    Usage:
        llm = get_llm()                              # uses SMART_MODEL
        llm = get_llm(model=FAST_MODEL)              # uses fast 8B model
        response = llm.invoke("What is Python?")
    """
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model=model or SMART_MODEL,
        temperature=temperature,
    )


def get_llm_fast(temperature: float = 0.0) -> ChatGroq:
    """
    Get the fast 8B model instance.
    Use for: intent classification, simple yes/no decisions,
             parameter extraction, calculator result formatting.
    Saves ~70% of tokens vs the 70B model for these tasks.
    """
    return get_llm(temperature=temperature, model=FAST_MODEL)


def get_llm_response(
    prompt:         str,
    system_message: str   = None,
    temperature:    float = 0.2,
    model:          str   = None,
) -> str:
    """
    Get a single LLM response (no conversation history).

    Args:
        prompt:         User's question / input
        system_message: System prompt to set behaviour (optional)
        temperature:    Response creativity (0–1)
        model:          Groq model name

    Returns:
        str: LLM's response text, or a "⚠️ …" error string on failure

    Usage:
        response = get_llm_response("What is a list in Python?")

        response = get_llm_response(
            prompt="Explain this error",
            system_message="You are a Python tutor"
        )
    """
    llm      = get_llm(temperature=temperature, model=model or SMART_MODEL)
    messages = []

    if system_message:
        messages.append(SystemMessage(content=system_message))

    messages.append(HumanMessage(content=prompt))

    return _invoke_with_retry(llm, messages, attempt_label="get_llm_response")


def get_llm_response_with_history(
    prompt:         str,
    chat_history:   list,
    system_message: str   = None,
    temperature:    float = 0.2,
    model:          str   = None,
) -> str:
    """
    Get an LLM response that includes prior conversation history.

    Args:
        prompt:       Current user input
        chat_history: List of prior messages in format:
                      [{"role": "user"|"assistant", "content": "…"}, …]
        system_message: System prompt (optional)
        temperature:  Response creativity (0–1)
        model:        Groq model name

    Returns:
        str: LLM's response text, or a "⚠️ …" error string on failure

    Usage:
        history = [
            {"role": "user",      "content": "What is a variable?"},
            {"role": "assistant", "content": "A variable is…"},
        ]
        response = get_llm_response_with_history(
            prompt="Can you give an example?",
            chat_history=history,
            system_message="You are a Python tutor"
        )
    """
    llm      = get_llm(temperature=temperature, model=model or SMART_MODEL)
    messages = []

    if system_message:
        messages.append(SystemMessage(content=system_message))

    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=prompt))

    return _invoke_with_retry(llm, messages, attempt_label="get_llm_response_with_history")


# ── Stats for app.py sidebar gauge ───────────────────────────────────────────

def get_usage_stats() -> dict:
    """
    Return token usage stats for the sidebar progress bar in app.py.

    Returns:
        {
            "tokens_last_minute": int,
            "warn_threshold":     int,
        }
    """
    return {
        "tokens_last_minute": _usage.tokens_last_minute(),
        "warn_threshold":     _usage.WARN_TOKENS_PER_MIN,
    }