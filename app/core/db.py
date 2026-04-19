"""PostgreSQL helpers for concierge state and traces."""

from __future__ import annotations

from typing import Any

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import DATABASE_URL
from app.schemas.common import A2AContext
from app.core.utils import now_iso


def get_connection() -> psycopg.Connection[Any]:
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except psycopg.Error as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Concierge database unavailable: {exc}",
        ) from exc


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS concierge_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    last_input TEXT NOT NULL,
                    last_intent TEXT NOT NULL,
                    session_summary TEXT,
                    last_response JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE concierge_sessions
                ADD COLUMN IF NOT EXISTS session_summary TEXT
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_traces (
                    id BIGSERIAL PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    session_id TEXT,
                    workflow_id TEXT,
                    trace_id TEXT,
                    step_name TEXT NOT NULL,
                    step_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_payload JSONB,
                    output_payload JSONB,
                    error_message TEXT,
                    model_name TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()


def persist_session(
    session_id: str,
    user_id: str,
    last_input: str,
    last_intent: str,
    last_response: dict[str, Any],
    session_summary: str | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO concierge_sessions (
                    session_id, user_id, last_input, last_intent, session_summary, last_response, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    last_input = EXCLUDED.last_input,
                    last_intent = EXCLUDED.last_intent,
                    session_summary = EXCLUDED.session_summary,
                    last_response = EXCLUDED.last_response,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    session_id,
                    user_id,
                    last_input,
                    last_intent,
                    session_summary,
                    Jsonb(last_response),
                    now_iso(),
                ),
            )
        conn.commit()


def fetch_session(session_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, user_id, last_input, last_intent, session_summary, last_response, updated_at
                FROM concierge_sessions
                WHERE session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def record_trace(
    *,
    service_name: str,
    context: A2AContext | None,
    step_name: str,
    step_type: str,
    status: str,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
    model_name: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_traces (
                    service_name, session_id, workflow_id, trace_id,
                    step_name, step_type, status, input_payload, output_payload,
                    error_message, model_name, prompt_tokens, completion_tokens, total_tokens
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    service_name,
                    context.session_id if context else None,
                    context.workflow_id if context else None,
                    context.trace_id if context else None,
                    step_name,
                    step_type,
                    status,
                    Jsonb(input_payload) if input_payload is not None else None,
                    Jsonb(output_payload) if output_payload is not None else None,
                    error_message,
                    model_name,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                ),
            )
        conn.commit()


def fetch_traces(session_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT service_name, session_id, workflow_id, trace_id, step_name, step_type, status,
                       input_payload, output_payload, error_message, model_name,
                       prompt_tokens, completion_tokens, total_tokens, created_at
                FROM workflow_traces
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            )
            return cur.fetchall()
