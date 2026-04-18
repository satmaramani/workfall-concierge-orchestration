"""FastAPI entrypoint for concierge orchestration."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.db import init_db
from app.graphs.graph import build_concierge_graph, run_concierge_graph
from app.services.intent_service import build_transformer_classifier
from app.schemas.workflow import WorkflowRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        app.state.db_available = True
    except Exception:
        app.state.db_available = False

    try:
        app.state.intent_classifier = build_transformer_classifier()
        app.state.transformer_available = app.state.intent_classifier is not None
    except Exception:
        app.state.intent_classifier = None
        app.state.transformer_available = False

    app.state.concierge_graph = build_concierge_graph(app.state.intent_classifier)
    yield


app = FastAPI(title="Concierge Orchestration", version="0.2.0", lifespan=lifespan)
app.state.db_available = False
app.state.transformer_available = False
app.state.intent_classifier = None
app.state.concierge_graph = None
app.include_router(router)


async def orchestrate(workflow_request: WorkflowRequest) -> dict:
    graph = app.state.concierge_graph or build_concierge_graph(app.state.intent_classifier)
    return await run_concierge_graph(graph, workflow_request)
