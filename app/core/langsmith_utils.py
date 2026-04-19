from __future__ import annotations

from openai import OpenAI

from app.core.config import LANGSMITH_API_KEY, LANGSMITH_TRACING


def maybe_wrap_openai(client: OpenAI) -> OpenAI:
    if not LANGSMITH_TRACING or not LANGSMITH_API_KEY:
        return client
    try:
        from langsmith.wrappers import wrap_openai

        return wrap_openai(client)
    except Exception:
        return client
