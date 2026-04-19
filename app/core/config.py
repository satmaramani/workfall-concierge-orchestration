"""Runtime configuration for concierge orchestration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


SERVICE_NAME = os.getenv("SERVICE_NAME", "concierge-orchestration")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
INVENTORY_BASE_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8001")
INVOICE_BASE_URL = os.getenv("INVOICE_BASE_URL", "http://localhost:8002")
MARKET_INTELLIGENCE_BASE_URL = os.getenv("MARKET_INTELLIGENCE_BASE_URL", "http://localhost:8003")
A2A_SHARED_TOKEN = os.getenv("A2A_SHARED_TOKEN", "")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://workfall:workfall@localhost:5432/workfall_multi_agent",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "none")
TRANSFORMER_ENABLED = os.getenv("TRANSFORMER_ENABLED", "true").lower() == "true"
TRANSFORMER_MODEL = os.getenv("TRANSFORMER_MODEL", "facebook/bart-large-mnli")
INTENT_CONFIDENCE_THRESHOLD = float(os.getenv("INTENT_CONFIDENCE_THRESHOLD", "0.85"))
