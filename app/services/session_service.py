"""Session service helpers."""

from __future__ import annotations

from app.core.db import fetch_session, fetch_traces, persist_session
from app.services.memory_service import build_session_memory_text, summarize_session_memory


def get_session_memory(session_id: str | None) -> dict | None:
    # The returned shape is tuned for prompt-building, not as a full copy of the database row.
    if not session_id:
        return None
    session = fetch_session(session_id)
    if not session:
        return None
    last_response = session.get("last_response") or {}
    return {
        "session_id": session["session_id"],
        "user_id": session["user_id"],
        "last_input": session.get("last_input"),
        "last_intent": session.get("last_intent"),
        "session_summary": session.get("session_summary"),
        "last_response": last_response,
        "last_ai_parse": last_response.get("ai_parse") or {},
        "last_result_data": last_response.get("data") or {},
        "updated_at": session.get("updated_at"),
    }


def persist_session_with_summary(
    *,
    session_id: str,
    user_id: str,
    last_input: str,
    last_intent: str,
    last_response: dict,
    prior_session: dict | None,
) -> None:
    # We store both the full last response and a short rolling summary so future turns can stay cheap.
    memory_text = build_session_memory_text(
        prior_summary=(prior_session or {}).get("session_summary"),
        last_input=last_input,
        last_intent=last_intent,
        last_response=last_response,
    )
    session_summary = summarize_session_memory(memory_text)
    persist_session(
        session_id=session_id,
        user_id=user_id,
        last_input=last_input,
        last_intent=last_intent,
        last_response=last_response,
        session_summary=session_summary,
    )


__all__ = [
    "fetch_session",
    "fetch_traces",
    "persist_session",
    "get_session_memory",
    "persist_session_with_summary",
]
