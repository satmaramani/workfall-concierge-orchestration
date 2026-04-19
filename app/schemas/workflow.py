"""Workflow-facing schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    user_input: str
    session_id: str | None = None
    user_id: str = "demo-user"
    include_market_insights: bool = True


class ParsedIntent(BaseModel):
    intent: Literal["check_stock", "list_products", "market_analysis", "create_invoice", "unknown"]
    product_id: str | None = None
    product_name: str | None = None
    quantity: int = 1
    customer_name: str | None = None
    include_market_insights: bool = True
    confidence: float = Field(ge=0, le=1)
    clarification_needed: bool = False
    clarification_question: str | None = None


class WorkflowFailureResponse(BaseModel):
    status: Literal["failed"]
    session_id: str | None = None
    intent: str = "unknown"
    agents_used: list[str] = Field(default_factory=list)
    workflow_steps: list[dict] = Field(default_factory=list)
    message: str
    error_code: str
