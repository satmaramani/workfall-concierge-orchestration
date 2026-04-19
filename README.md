# Concierge Orchestration

Primary orchestration service for the multi-agent e-commerce system. This repo is the central entrypoint for user requests and multi-agent workflow execution.

## What This Service Does

- interprets user requests and resolves intent
- loads and reuses session context across follow-up interactions
- orchestrates Inventory, Invoice, and Market Intelligence via A2A-style communication
- runs graph-based workflow control with LangGraph
- aggregates downstream results into a structured workflow response
- persists session memory and workflow traces in PostgreSQL

## Default Port

`8000`

## Local Base URL

`http://localhost:8000`

## Depends On

- `inventory-agent` on `8001`
- `invoice-agent` on `8002`
- `market-intelligence-agent` on `8003`
- PostgreSQL on `5432`
- OpenAI API key for fallback parsing

## PostgreSQL Requirement

This service expects PostgreSQL to already be running before startup.

Recommended local database settings:

- host: `localhost`
- port: `5432`
- database: `workfall_multi_agent`
- user: `workfall`
- password: `workfall`

Tables are created automatically on startup. You do not need to manually create Concierge tables if the configured database is reachable and the user has permission to create tables.

## Tech Used Here

- FastAPI
- LangGraph
- OpenAI Python SDK
- PostgreSQL via `psycopg`
- optional transformer-based intent classification
- Sumy-based rolling memory summarization

## Environment Setup

1. Copy the example file:

```powershell
copy .env.example .env
```

2. Update values if needed, especially:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- downstream service URLs if your ports differ

Example:

```env
DATABASE_URL=postgresql://workfall:workfall@localhost:5432/workfall_multi_agent
```

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run Locally

```powershell
uvicorn app.main:app --reload --port 8000
```

## Key Endpoints

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `POST /api/v1/workflows/request`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/traces/{session_id}`
- `POST /api/v1/a2a/request`

## Expected Local Startup Order

1. PostgreSQL
2. `inventory-agent`
3. `market-intelligence-agent`
4. `invoice-agent`
5. `concierge-orchestration`
6. optional `streamlit-ui`

## Repo Structure

```text
concierge-orchestration/
  app/
    api/
    clients/
    core/
    graphs/
    schemas/
    services/
  tests/
  .env.example
  requirements.txt
  .gitignore
  README.md
```

## Notes

- session continuity is driven by `session_id`
- transformer parsing is optional and falls back to OpenAI
- this service is the main LangGraph orchestration layer in the system
