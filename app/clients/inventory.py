"""Inventory service client."""

from __future__ import annotations

import httpx

from app.core.config import INVENTORY_BASE_URL


async def fetch_inventory_catalog() -> list[dict]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{INVENTORY_BASE_URL}/api/v1/products")
        response.raise_for_status()
        return response.json().get("products", [])
