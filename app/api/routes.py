"""FastAPI routes for concierge orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import (
    INTENT_CONFIDENCE_THRESHOLD,
    INVENTORY_BASE_URL,
    INVOICE_BASE_URL,
    MARKET_INTELLIGENCE_BASE_URL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    SERVICE_NAME,
    SERVICE_PORT,
    LANGSMITH_TRACING,
    LANGSMITH_PROJECT,
    TRANSFORMER_ENABLED,
    TRANSFORMER_MODEL,
)
from app.core.security import require_agent_token, require_api_token
from app.core.utils import now_iso
from app.schemas.common import A2AError, A2AMeta, A2ARequest, A2AResponse
from app.schemas.workflow import WorkflowFailureResponse, WorkflowRequest
from app.services.session_service import fetch_session, fetch_traces


def get_orchestrator():
    # Import lazily to avoid circular imports during app startup.
    from app.main import orchestrate

    return orchestrate


router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    from app.main import app
    db_available = app.state.db_available
    transformer_enabled = TRANSFORMER_ENABLED
    transformer_available = app.state.transformer_available
    openai_configured = bool(OPENAI_API_KEY)
    status_value = "ok"
    if not db_available:
        status_value = "degraded"
    elif transformer_enabled and not transformer_available and not openai_configured:
        status_value = "degraded"

    return {
        "status": status_value,
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "inventory_base_url": INVENTORY_BASE_URL,
        "invoice_base_url": INVOICE_BASE_URL,
        "market_base_url": MARKET_INTELLIGENCE_BASE_URL,
        "db_available": db_available,
        "openai_configured": openai_configured,
        "transformer_enabled": transformer_enabled,
        "transformer_available": transformer_available,
        "transformer_model": TRANSFORMER_MODEL,
        "intent_confidence_threshold": INTENT_CONFIDENCE_THRESHOLD,
        "model": OPENAI_MODEL,
        "langgraph_enabled": True,
        "langsmith_tracing": LANGSMITH_TRACING,
        "langsmith_project": LANGSMITH_PROJECT if LANGSMITH_TRACING else None,
        "timestamp": now_iso(),
    }


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "service": SERVICE_NAME,
        "intents": ["check_stock", "list_products", "market_analysis", "create_invoice"],
    }


@router.post("/workflows/request")
async def workflow_request(
    request: WorkflowRequest,
    x_api_token: str | None = Header(default=None),
    orchestrate=Depends(get_orchestrator),
) -> dict:
    require_api_token(x_api_token)
    try:
        return await orchestrate(request)
    except HTTPException:
        raise
    except Exception as exc:
        # This fallback keeps the UI structured even if an unexpected exception slips through.
        return WorkflowFailureResponse(
            status="failed",
            session_id=request.session_id,
            agents_used=["concierge"],
            workflow_steps=[
                {
                    "agent": "concierge",
                    "intent": "workflow_execution",
                    "status": "failed",
                    "error": str(exc),
                }
            ],
            message="Concierge workflow failed unexpectedly. Check downstream services and traces.",
            error_code="workflow_execution_error",
        ).model_dump()


@router.get("/sessions/{session_id}")
def get_session(session_id: str, x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
    session = fetch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/traces/{session_id}")
def get_traces(session_id: str, x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
    rows = fetch_traces(session_id)
    # Traces are normalized here so the UI does not need to know about database timestamp objects.
    return {
        "session_id": session_id,
        "events": [{**row, "created_at": row["created_at"].isoformat()} for row in rows],
    }


@router.post("/a2a/request", response_model=A2AResponse)
async def a2a_request(
    request: A2ARequest,
    x_agent_token: str | None = Header(default=None),
    orchestrate=Depends(get_orchestrator),
) -> A2AResponse:
    require_agent_token(x_agent_token)
    try:
        workflow_request = WorkflowRequest(
            user_input=request.payload.get("user_input", ""),
            session_id=request.context.session_id,
            user_id=request.context.user_id or "demo-user",
            include_market_insights=request.payload.get("include_market_insights", True),
        )
        result = await orchestrate(workflow_request)
        return A2AResponse(
            request_id=request.request_id,
            status="success",
            agent="concierge",
            result=result,
            error=None,
            meta=A2AMeta(
                retry_count=0,
                timestamp=now_iso(),
                source_service=SERVICE_NAME,
                target_service="caller",
            ),
        )
    except HTTPException as exc:
        return A2AResponse(
            request_id=request.request_id,
            status="failed",
            agent="concierge",
            result=None,
            error=A2AError(code="CONCIERGE_ERROR", message=str(exc.detail), retriable=exc.status_code >= 500),
            meta=A2AMeta(
                retry_count=0,
                timestamp=now_iso(),
                source_service=SERVICE_NAME,
                target_service="caller",
            ),
        )
