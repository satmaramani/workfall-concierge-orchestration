# Concierge Orchestration

Primary user-facing orchestration service for the multi-agent e-commerce system.

## Responsibilities

- accept user requests
- classify intent and extract entities
- orchestrate cross-agent workflows
- maintain workflow context
- aggregate downstream outputs into a structured response

## AI And Persistence

- uses a transformer classifier first for intent detection
- uses OpenAI Responses API for structured intent and entity parsing
- falls back to OpenAI when transformer confidence is low or product resolution is ambiguous
- persists session context in PostgreSQL
- resolves products from the live Inventory catalog instead of hardcoded mappings

## Default Port

`8000`

## Local Run Target

`http://localhost:8000`

## Planned Dependencies

- FastAPI
- Uvicorn
- Pydantic
- httpx
- LangGraph
- LangChain
- optional transformers and LLM integrations

## Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

Set these first:

- `OPENAI_API_KEY`
- `DATABASE_URL`

## Key Endpoints

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `POST /api/v1/workflows/request`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/a2a/request`

## Repo Layout

```text
concierge-orchestration/
  app/
    api/
    clients/
    core/
    models/
    schemas/
    services/
    agents/
    graphs/
  tests/
  .env.example
  requirements.txt
  .gitignore
  README.md
```
