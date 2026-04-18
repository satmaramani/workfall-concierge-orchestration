"""A2A client helpers."""

from __future__ import annotations

from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.core.config import SERVICE_NAME
from app.core.db import record_trace
from app.core.security import make_headers
from app.schemas.common import A2AContext, A2ARequest


async def call_agent(base_url: str, intent: str, payload: dict, context: A2AContext) -> dict:
    request = A2ARequest(
        request_id=str(uuid4()),
        source_agent="concierge",
        target_agent=base_url,
        intent=intent,
        context=context,
        payload=payload,
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base_url}/api/v1/a2a/request",
            json=request.model_dump(),
            headers=make_headers(),
        )
        response.raise_for_status()
        result = response.json()
        record_trace(
            service_name=SERVICE_NAME,
            context=context,
            step_name=f"a2a_{intent}",
            step_type="a2a_call",
            status=result.get("status", "success"),
            input_payload={"base_url": base_url, "intent": intent, "payload": payload},
            output_payload=result,
        )
        return result


async def call_agent_with_retry(
    base_url: str,
    intent: str,
    payload: dict,
    context: A2AContext,
    max_attempts: int = 2,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await call_agent(base_url, intent, payload, context)
            if response.get("status") == "failed" and response.get("error", {}).get("retriable"):
                last_error = HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=response["error"]["message"],
                )
                continue
            return response
        except (httpx.HTTPError, HTTPException) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
    if isinstance(last_error, HTTPException):
        raise last_error
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"A2A communication failed for intent '{intent}'",
    ) from last_error
