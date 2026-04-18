"""Intent parsing services."""

from __future__ import annotations

import difflib
import logging

from fastapi import HTTPException, status
from openai import OpenAI

from app.core.config import (
    INTENT_CONFIDENCE_THRESHOLD,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    SERVICE_NAME,
    TRANSFORMER_ENABLED,
    TRANSFORMER_MODEL,
)
from app.core.db import record_trace
from app.schemas.common import A2AContext
from app.schemas.workflow import ParsedIntent

logger = logging.getLogger(__name__)


def build_transformer_classifier():
    if not TRANSFORMER_ENABLED:
        return None
    try:
        from transformers import pipeline

        return pipeline("zero-shot-classification", model=TRANSFORMER_MODEL)
    except Exception as exc:  # pragma: no cover
        logger.warning("Transformer classifier unavailable; falling back to OpenAI parsing only: %s", exc)
        return None


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured for Concierge",
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def resolve_product_from_text(user_input: str, products: list[dict]) -> dict | None:
    text = user_input.lower()
    candidates: dict[str, dict] = {}
    for product in products:
        candidates[product["product_id"].lower()] = product
        candidates[product["product_name"].lower()] = product
        for token in product["product_name"].lower().replace("-", " ").split():
            if len(token) > 3:
                candidates[token] = product

    for key, product in candidates.items():
        if key in text:
            return product

    close_matches = difflib.get_close_matches(text, list(candidates.keys()), n=1, cutoff=0.45)
    if close_matches:
        return candidates[close_matches[0]]
    return None


def parse_with_transformer(user_input: str, products: list[dict], classifier, context: A2AContext) -> ParsedIntent | None:
    if not TRANSFORMER_ENABLED or not classifier:
        record_trace(
            service_name=SERVICE_NAME,
            context=context,
            step_name="transformer_parse",
            step_type="ai_call",
            status="skipped",
            input_payload={"reason": "transformer unavailable or disabled"},
        )
        return None

    labels = {
        "create_invoice": "Create an invoice or bill for products",
        "check_stock": "Check stock, inventory availability, or quantity",
        "market_analysis": "Analyze market trends, competitor pricing, or demand signals",
        "list_products": "List products or show the product catalog",
        "unknown": "The request is unclear or unsupported",
    }
    result = classifier(user_input, list(labels.values()), multi_label=False)
    top_label = result["labels"][0]
    confidence = float(result["scores"][0])
    label_to_intent = {value: key for key, value in labels.items()}
    intent = label_to_intent[top_label]

    quantity = 1
    quantity_tokens = [token for token in user_input.replace(",", " ").split() if token.isdigit()]
    if quantity_tokens:
        quantity = int(quantity_tokens[0])

    product = resolve_product_from_text(user_input, products)
    clarification_needed = intent in {"check_stock", "market_analysis", "create_invoice"} and product is None
    parsed = ParsedIntent(
        intent=intent,
        product_id=product["product_id"] if product else None,
        product_name=product["product_name"] if product else None,
        quantity=quantity,
        customer_name=None,
        include_market_insights=True,
        confidence=confidence,
        clarification_needed=clarification_needed,
        clarification_question=("Which product do you want to use for this request?" if clarification_needed else None),
    )
    record_trace(
        service_name=SERVICE_NAME,
        context=context,
        step_name="transformer_parse",
        step_type="ai_call",
        status="success",
        input_payload={"user_input": user_input, "product_count": len(products)},
        output_payload=parsed.model_dump(),
        model_name=TRANSFORMER_MODEL,
    )
    return parsed


def parse_request_with_ai(
    user_input: str,
    products: list[dict],
    include_market_insights: bool,
    context: A2AContext,
) -> ParsedIntent:
    client = get_openai_client()
    product_catalog = [
        {
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "quantity": item["quantity"],
        }
        for item in products
    ]
    system_prompt = (
        "You are the Concierge Agent for an internal multi-agent e-commerce system. "
        "Classify the user's intent and extract structured fields. "
        "Allowed intents are: check_stock, list_products, market_analysis, create_invoice, unknown. "
        "Only return a product_id if it exists in the provided catalog. "
        "If the request is ambiguous, set clarification_needed to true and provide a short clarification_question."
    )
    user_message = {
        "user_input": user_input,
        "include_market_insights_requested": include_market_insights,
        "product_catalog": product_catalog,
    }
    response = client.responses.parse(
        model=OPENAI_MODEL,
        reasoning={"effort": OPENAI_REASONING_EFFORT},
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(user_message)},
        ],
        text_format=ParsedIntent,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI could not parse the concierge request",
        )
    usage = getattr(response, "usage", None)
    record_trace(
        service_name=SERVICE_NAME,
        context=context,
        step_name="openai_parse",
        step_type="ai_call",
        status="success",
        input_payload={
            "user_input": user_input,
            "include_market_insights": include_market_insights,
            "product_catalog_size": len(product_catalog),
        },
        output_payload=parsed.model_dump(),
        model_name=OPENAI_MODEL,
        prompt_tokens=getattr(usage, "input_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "output_tokens", None) if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
    )
    return parsed


def should_use_transformer(parse: dict | None) -> bool:
    return bool(
        parse
        and parse["confidence"] >= INTENT_CONFIDENCE_THRESHOLD
        and not parse["clarification_needed"]
    )
