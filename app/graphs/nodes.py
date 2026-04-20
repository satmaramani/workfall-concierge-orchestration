"""LangGraph nodes and routing for Concierge."""

from __future__ import annotations

from app.clients.a2a import call_agent_with_retry
from app.clients.inventory import fetch_inventory_catalog
from app.core.config import (
    INVENTORY_BASE_URL,
    INVOICE_BASE_URL,
    MARKET_INTELLIGENCE_BASE_URL,
    SERVICE_NAME,
)
from app.core.db import record_trace
from app.services.intent_service import parse_request_with_ai, parse_with_transformer, should_use_transformer
from app.services.session_service import get_session_memory, persist_session_with_summary


def node_load_session_context(state):
    # Session memory is loaded first so follow-up prompts can reuse the previous product or intent.
    prior_session = get_session_memory(state["session_id"])
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="load_session_context",
        step_type="graph_node",
        status="success",
        input_payload={"session_id": state["session_id"]},
        output_payload={
            "has_prior_session": bool(prior_session),
            "last_intent": prior_session.get("last_intent") if prior_session else None,
            "session_summary": prior_session.get("session_summary") if prior_session else None,
        },
    )
    return {"prior_session": prior_session}


async def node_fetch_inventory_catalog(state):
    # Concierge keeps a local copy of the catalog for intent parsing instead of asking Inventory repeatedly.
    products = await fetch_inventory_catalog()
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="fetch_inventory_catalog",
        step_type="graph_node",
        status="success",
        input_payload={"inventory_base_url": INVENTORY_BASE_URL},
        output_payload={"product_count": len(products)},
    )
    return {"products": products, "agents_used": [], "workflow_steps": []}


def node_transformer_parse(state, classifier):
    workflow_request = state["workflow_request"]
    products = state.get("products", [])
    transformer_parse = parse_with_transformer(
        workflow_request.user_input,
        products,
        classifier,
        state["context"],
        state.get("prior_session"),
    )
    return {"transformer_parse": transformer_parse.model_dump() if transformer_parse else None}


def route_after_transformer(state):
    return "use_transformer" if should_use_transformer(state.get("transformer_parse")) else "openai_parse"


def node_use_transformer_parse(state):
    # Once the transformer path is chosen, we persist that decision into the trace for later debugging.
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="intent_gate",
        step_type="graph_node",
        status="success",
        input_payload={"backend": "transformer"},
        output_payload=state["transformer_parse"],
    )
    return {"parsed": state["transformer_parse"], "intent_resolution_backend": "transformer"}


def node_openai_parse(state):
    workflow_request = state["workflow_request"]
    parsed = parse_request_with_ai(
        workflow_request.user_input,
        state.get("products", []),
        workflow_request.include_market_insights,
        state["context"],
        state.get("prior_session"),
    )
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="intent_gate",
        step_type="graph_node",
        status="success",
        input_payload={"backend": "openai_fallback"},
        output_payload=parsed.model_dump(),
    )
    return {"parsed": parsed.model_dump(), "intent_resolution_backend": "openai"}


def route_after_parse(state):
    # The graph separates "unclear request" from "known intent but missing product" for better UX.
    parsed = state.get("parsed") or {}
    if parsed.get("intent") == "unknown" or parsed.get("clarification_needed"):
        return "clarification"
    if parsed.get("intent") in {"check_stock", "market_analysis", "create_invoice"} and not parsed.get("product_id"):
        return "missing_product"
    return "route_intent"


def node_clarification_failure(state):
    parsed = state["parsed"]
    result = {
        "status": "failed",
        "session_id": state["session_id"],
        "intent": parsed["intent"],
        "agents_used": [],
        "clarification_needed": parsed["clarification_needed"],
        "message": parsed.get("clarification_question")
        or "Unable to confidently route the request. Please rephrase with product and action details.",
        "ai_parse": parsed,
        "intent_resolution_backend": state.get("intent_resolution_backend"),
        "transformer_parse": state.get("transformer_parse"),
    }
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="clarification_failure",
        step_type="graph_node",
        status="failed",
        input_payload={"parsed": parsed},
        output_payload=result,
        error_message=result["message"],
    )
    return {"result": result, "should_persist": True, "error_message": result["message"], "error_code": "clarification_required"}


def node_missing_product_failure(state):
    parsed = state["parsed"]
    result = {
        "status": "failed",
        "session_id": state["session_id"],
        "intent": parsed["intent"],
        "agents_used": [],
        "message": "A matching product could not be resolved from inventory. Add the product first or be more specific.",
        "ai_parse": parsed,
        "intent_resolution_backend": state.get("intent_resolution_backend"),
        "transformer_parse": state.get("transformer_parse"),
    }
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="missing_product_failure",
        step_type="graph_node",
        status="failed",
        input_payload={"parsed": parsed},
        output_payload=result,
        error_message=result["message"],
    )
    return {"result": result, "should_persist": True, "error_message": result["message"], "error_code": "missing_product"}


def node_route_intent(state):
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="route_intent",
        step_type="graph_node",
        status="success",
        input_payload={"intent": state["parsed"]["intent"]},
    )
    return {}


def route_by_intent(state):
    return str(state["parsed"]["intent"])


async def node_check_stock(state):
    parsed = state["parsed"]
    response = await call_agent_with_retry(
        INVENTORY_BASE_URL,
        "check_stock",
        {"product_id": parsed["product_id"], "quantity": parsed["quantity"]},
        state["context"],
    )
    return {
        "agents_used": ["inventory"],
        "workflow_steps": [{"agent": "inventory", "intent": "check_stock", "status": response["status"]}],
        "final_data": response["result"],
    }


async def node_list_products(state):
    response = await call_agent_with_retry(INVENTORY_BASE_URL, "list_products", {}, state["context"])
    return {
        "agents_used": ["inventory"],
        "workflow_steps": [{"agent": "inventory", "intent": "list_products", "status": response["status"]}],
        "final_data": response["result"],
    }


async def node_market_analysis(state):
    parsed = state["parsed"]
    response = await call_agent_with_retry(
        MARKET_INTELLIGENCE_BASE_URL,
        "market_analysis",
        {"product_id": parsed["product_id"]},
        state["context"],
    )
    return {
        "agents_used": ["market-intelligence"],
        "workflow_steps": [{"agent": "market-intelligence", "intent": "market_analysis", "status": response["status"]}],
        "final_data": response["result"],
    }


async def node_create_invoice(state):
    parsed = state["parsed"]
    workflow_request = state["workflow_request"]
    payload = {
        "items": [{"product_id": parsed["product_id"], "quantity": parsed["quantity"]}],
        "customer_name": parsed.get("customer_name") or "Internal Demo Customer",
        "include_market_insights": parsed.get("include_market_insights", True)
        and workflow_request.include_market_insights,
    }
    response = await call_agent_with_retry(INVOICE_BASE_URL, "create_invoice", payload, state["context"])
    invoice_result = response["result"]
    downstream_agents = invoice_result.get("downstream_agents_used", [])
    downstream_steps = invoice_result.get("workflow_steps", [])
    # Concierge reports both its own invoice call and the nested downstream steps surfaced by Invoice.
    return {
        "agents_used": list(dict.fromkeys(["invoice", *downstream_agents])),
        "workflow_steps": [
            {
                "agent": "invoice",
                "intent": "create_invoice",
                "status": response["status"],
                "notes": "Invoice service orchestrated downstream inventory and market steps.",
            }
        ]
        + downstream_steps,
        "final_data": invoice_result,
    }


def node_aggregate_success(state):
    parsed = state["parsed"]
    result = {
        "status": "success",
        "session_id": state["session_id"],
        "intent": parsed["intent"],
        "agents_used": state.get("agents_used", []),
        "workflow_steps": state.get("workflow_steps", []),
        "data": state.get("final_data"),
        "ai_parse": parsed,
        "intent_resolution_backend": state.get("intent_resolution_backend"),
        "transformer_parse": state.get("transformer_parse"),
        "message": f"Request routed successfully for intent '{parsed['intent']}'.",
    }
    record_trace(
        service_name=SERVICE_NAME,
        context=state["context"],
        step_name="aggregate_success",
        step_type="graph_node",
        status="success",
        input_payload={"intent": parsed["intent"]},
        output_payload=result,
    )
    return {"result": result, "should_persist": True}


def node_persist_result(state):
    workflow_request = state["workflow_request"]
    parsed = state.get("parsed") or {"intent": "unknown"}
    if state.get("should_persist"):
        # Persisting after both success and controlled failure keeps follow-up turns grounded in real outcomes.
        persist_session_with_summary(
            session_id=state["session_id"],
            user_id=workflow_request.user_id,
            last_input=workflow_request.user_input,
            last_intent=parsed["intent"],
            last_response=state["result"],
            prior_session=state.get("prior_session"),
        )
        record_trace(
            service_name=SERVICE_NAME,
            context=state["context"],
            step_name="persist_result",
            step_type="graph_node",
            status="success",
            input_payload={"session_id": state["session_id"]},
        )
    return {}
