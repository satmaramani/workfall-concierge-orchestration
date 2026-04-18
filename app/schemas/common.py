"""Shared A2A schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class A2AContext(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    workflow_id: str | None = None
    trace_id: str | None = None


class A2ARequest(BaseModel):
    request_id: str
    source_agent: str
    target_agent: str
    intent: str
    context: A2AContext = Field(default_factory=A2AContext)
    capabilities: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class A2AError(BaseModel):
    code: str
    message: str
    retriable: bool = False


class A2AMeta(BaseModel):
    retry_count: int = 0
    timestamp: str
    source_service: str
    target_service: str


class A2AResponse(BaseModel):
    request_id: str
    status: str
    agent: str
    result: dict[str, Any] | None = None
    error: A2AError | None = None
    meta: A2AMeta
