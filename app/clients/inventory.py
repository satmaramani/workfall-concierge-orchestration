"""Inventory service client."""

from __future__ import annotations

import httpx

from app.core.config import API_SHARED_TOKEN, INVENTORY_BASE_URL


def _headers() -> dict[str, str]:
    # Inventory's public endpoints are token-protected, so Concierge forwards the shared UI/API token here.
    headers: dict[str, str] = {}
    if API_SHARED_TOKEN:
        headers["X-API-Token"] = API_SHARED_TOKEN
    return headers


async def fetch_inventory_catalog() -> list[dict]:
    # Concierge reads the full catalog once per request to support product resolution in intent parsing.
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{INVENTORY_BASE_URL}/api/v1/products",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json().get("products", [])
