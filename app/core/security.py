"""Security helpers for service-to-service auth."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.config import A2A_SHARED_TOKEN


def require_agent_token(x_agent_token: str | None) -> None:
    if A2A_SHARED_TOKEN and x_agent_token != A2A_SHARED_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Agent-Token header",
        )


def make_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if A2A_SHARED_TOKEN:
        headers["X-Agent-Token"] = A2A_SHARED_TOKEN
    return headers
