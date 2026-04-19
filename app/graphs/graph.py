"""Graph assembly and orchestration entrypoint."""

from __future__ import annotations

from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.graphs.nodes import (
    node_aggregate_success,
    node_check_stock,
    node_clarification_failure,
    node_create_invoice,
    node_fetch_inventory_catalog,
    node_load_session_context,
    node_list_products,
    node_market_analysis,
    node_missing_product_failure,
    node_openai_parse,
    node_persist_result,
    node_route_intent,
    node_transformer_parse,
    node_use_transformer_parse,
    route_after_parse,
    route_after_transformer,
    route_by_intent,
)
from app.graphs.state import ConciergeGraphState
from app.schemas.common import A2AContext


def build_concierge_graph(classifier):
    graph = StateGraph(ConciergeGraphState)
    graph.add_node("load_session_context", node_load_session_context)
    graph.add_node("fetch_inventory_catalog", node_fetch_inventory_catalog)
    graph.add_node("transformer_parse", lambda state: node_transformer_parse(state, classifier))
    graph.add_node("use_transformer_parse", node_use_transformer_parse)
    graph.add_node("openai_parse", node_openai_parse)
    graph.add_node("clarification_failure", node_clarification_failure)
    graph.add_node("missing_product_failure", node_missing_product_failure)
    graph.add_node("route_intent", node_route_intent)
    graph.add_node("check_stock", node_check_stock)
    graph.add_node("list_products", node_list_products)
    graph.add_node("market_analysis", node_market_analysis)
    graph.add_node("create_invoice", node_create_invoice)
    graph.add_node("aggregate_success", node_aggregate_success)
    graph.add_node("persist_result", node_persist_result)

    graph.add_edge(START, "load_session_context")
    graph.add_edge("load_session_context", "fetch_inventory_catalog")
    graph.add_edge("fetch_inventory_catalog", "transformer_parse")
    graph.add_conditional_edges(
        "transformer_parse",
        route_after_transformer,
        {"use_transformer": "use_transformer_parse", "openai_parse": "openai_parse"},
    )
    graph.add_conditional_edges(
        "use_transformer_parse",
        route_after_parse,
        {
            "clarification": "clarification_failure",
            "missing_product": "missing_product_failure",
            "route_intent": "route_intent",
        },
    )
    graph.add_conditional_edges(
        "openai_parse",
        route_after_parse,
        {
            "clarification": "clarification_failure",
            "missing_product": "missing_product_failure",
            "route_intent": "route_intent",
        },
    )
    graph.add_conditional_edges(
        "route_intent",
        route_by_intent,
        {
            "check_stock": "check_stock",
            "list_products": "list_products",
            "market_analysis": "market_analysis",
            "create_invoice": "create_invoice",
        },
    )
    graph.add_edge("check_stock", "aggregate_success")
    graph.add_edge("list_products", "aggregate_success")
    graph.add_edge("market_analysis", "aggregate_success")
    graph.add_edge("create_invoice", "aggregate_success")
    graph.add_edge("aggregate_success", "persist_result")
    graph.add_edge("clarification_failure", "persist_result")
    graph.add_edge("missing_product_failure", "persist_result")
    graph.add_edge("persist_result", END)
    return graph.compile()


async def run_concierge_graph(graph, workflow_request):
    session_id = workflow_request.session_id or str(uuid4())
    context = A2AContext(
        session_id=session_id,
        user_id=workflow_request.user_id,
        workflow_id=str(uuid4()),
        trace_id=str(uuid4()),
    )
    initial_state: ConciergeGraphState = {
        "workflow_request": workflow_request,
        "session_id": session_id,
        "context": context,
        "agents_used": [],
        "workflow_steps": [],
        "should_persist": False,
    }
    final_state = await graph.ainvoke(initial_state)
    return final_state["result"]
