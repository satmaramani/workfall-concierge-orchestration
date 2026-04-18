"""LangGraph state definitions."""

from __future__ import annotations

from typing import Any, TypedDict

from app.schemas.common import A2AContext
from app.schemas.workflow import WorkflowRequest


class ConciergeGraphState(TypedDict, total=False):
    workflow_request: WorkflowRequest
    session_id: str
    context: A2AContext
    products: list[dict[str, Any]]
    transformer_parse: dict[str, Any] | None
    parsed: dict[str, Any] | None
    intent_resolution_backend: str
    agents_used: list[str]
    workflow_steps: list[dict[str, Any]]
    final_data: dict[str, Any] | None
    result: dict[str, Any]
    error_message: str | None
    error_code: str | None
    should_persist: bool
