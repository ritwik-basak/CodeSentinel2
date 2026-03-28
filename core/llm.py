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
    Send ``prompt`` to the Groq LLM and sleep 1.5 s afterward so the next
    call respects Groq's rate limit.

    Returns the model's response as a plain string.
    """
    response = _get_llm().invoke(prompt)
    time.sleep(1.5)
    return response.content
