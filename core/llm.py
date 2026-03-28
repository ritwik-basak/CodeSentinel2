"""
llm.py — Shared Groq LLM instance and rate-limited invocation wrapper.

All agents must call ``rate_limited_invoke(prompt)`` rather than invoking
the LLM directly, to stay within Groq's API rate limits.

The LLM is initialised lazily on first use so that importing this module
never fails due to a missing GROQ_API_KEY.
"""

import os
import time

from langchain_groq import ChatGroq

_MODEL   = "llama-3.3-70b-versatile"
_llm: ChatGroq | None = None


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set. Add it to your .env file."
            )
        _llm = ChatGroq(api_key=api_key, model=_MODEL)
    return _llm


# ---------------------------------------------------------------------------
# Rate-limited wrapper — the only entry point agents should use
# ---------------------------------------------------------------------------

def rate_limited_invoke(prompt: str) -> str:
    """
    Send ``prompt`` to the Groq LLM and retry with exponential backoff on
    rate-limit errors (429 / 413). Sleeps 2 s between successful calls.

    Returns the model's response as a plain string.
    """
    wait = 15
    for attempt in range(5):
        try:
            response = _get_llm().invoke(prompt)
            time.sleep(5)
            return response.content
        except Exception as exc:
            msg = str(exc)
            if "rate_limit_exceeded" in msg or "413" in msg or "429" in msg:
                print(f"  [rate limit] waiting {wait}s before retry (attempt {attempt + 1}/5)...")
                time.sleep(wait)
                wait = min(wait * 2, 60)
            else:
                raise
    raise RuntimeError("Groq rate limit persisted after 5 retries.")
