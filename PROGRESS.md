# Museum Orchestration Build Progress

## Current Phase: 2
## Last Session: 2026-05-30
## Status: in-progress

## Completed

### Phase 1: Orchestration Core ✅
- `orchestrator/main.py` — FastAPI app with CORS + lifespan init
- `orchestrator/config.py` — pydantic-settings env var config
- `orchestrator/state/db.py` — SQLite init, get_db() context manager, WAL mode, 5-table schema
- `orchestrator/state/models.py` — Pydantic models: Persona, Job, AgentStats, TriggerRequest/Response
- `orchestrator/agents/base.py` — BaseAgent ABC
- `orchestrator/agents/registry.py` — AGENT_REGISTRY, PIPELINE_ORDER, get_agent(), list_agents()
- `orchestrator/agents/*.py` — 7 agent stubs with correct name/description/dependencies
- `orchestrator/queue/executor.py` — Full working job executor: queues jobs, runs agents, tracks timing, logs failures to error_log, marks persona complete/failed
- `orchestrator/api/routes.py` — 10 fully implemented endpoints
- `requirements.txt`, `Procfile`, `railway.toml`, `.env.example`, `.gitignore`

## Next Session: Phase 2 — Agent Integration

Wire each stub to real implementation in this order:

1. **persona_identifier** — validate slug, check SQLite + Pinecone for existing vectors
2. **corpus_fetcher** — read `sources.json`, download from Archive.org / Gutenberg / web
3. **corpus_cleaner** — text cleaning pipeline, 600t/100t chunking, write cleaned JSON
4. **pinecone_uploader** — Voyage AI embed (voyage-3-large, 2048-dim), upsert to `museum-of-minds` index
5. **page_generator** — render HTML from persona.json + hall template, commit to `jimmyardis/museum-of-minds`
6. **railway_deployer** — Railway GraphQL API: create service, set env vars, trigger deploy

Context for Phase 2:
- Existing downloader scripts at `/home/wner/execution/` (archive_downloader.py, gutenberg_downloader.py, corpus_cleaner.py)
- Pinecone filter syntax: `{"persona_id": pid}` (NOT `{"persona_id": {"$eq": pid}}`)
- Voyage AI model: `voyage-3-large`, 2048 dimensions
- Railway project for new personas: `giving-expression`
- Persona page templates in `jimmyardis/museum-of-minds` — match existing hall structure

## Notes
- Import verified: all 10 routes register cleanly
- Phase 1 executor is real code (not a stub) — runs agents, tracks all state in SQLite
- Phase 2 agents should import logic from existing `/home/wner/execution/` scripts where possible rather than rewriting from scratch
