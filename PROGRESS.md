# Museum Orchestration Build Progress

## Current Phase: 3
## Last Session: 2026-05-30
## Status: in-progress

## Completed

### Phase 1: Orchestration Core ✅
- FastAPI app with CORS, lifespan DB init
- 5-table SQLite schema + context manager
- Pydantic models (Persona, Job, AgentStats, Trigger*)
- BaseAgent ABC + 7 agent stubs in registry
- Full working job executor (state tracking, error logging, pipeline control)
- 10 REST endpoints (health, status, personas, jobs, memory, trigger, agents, sync)
- Railway config (railway.toml, Procfile), .env.example, .gitignore

### Phase 2: Agent Integration ✅
- **persona_identifier** — validates slug, reads persona.json, checks Pinecone vector count
- **corpus_fetcher** — downloads Archive.org (direct identifier or search) + Gutenberg (all URL patterns)
- **corpus_cleaner** — cleans OCR artifacts, normalizes whitespace, saves to corpus/cleaned/
- **pinecone_uploader** — Voyage AI voyage-3-large (2048-dim), 600t/100t chunking, Pinecone upsert in batches
- **page_generator** — commits persona HTML to jimmyardis/museum-of-minds via GitHub API (uses pre-built HTML or generates minimal template)
- **railway_deployer** — Railway GraphQL: serviceCreate → serviceConnect → domain → env vars → deploy trigger
- **tts_auditioner** — ElevenLabs preview clips for configured or candidate voices
- config.py expanded: museum_root, voyage_api_key, github_token/username, railway_project_id/environment_id

## Next Session: Phase 3 — Memory and Observability

1. **Pinecone sync on startup** — query Pinecone for all unique persona_ids and upsert into SQLite personas table (status=complete, vector_count populated)
2. **SSE endpoint for job progress** — `GET /jobs/{id}/stream` returns server-sent events as a job runs
3. **`/sync` endpoint (real impl)** — triggers Pinecone persona sync into SQLite
4. **System health metrics** — add per-agent avg run time, success rate to `/status`
5. **Startup persona census** — log how many personas + vectors exist at boot

## Notes
- All 7 agents import cleanly; pipeline order: identifier→fetcher→cleaner→uploader→page→railway
- page_generator prefers existing index.html from personas/{id}/ or museum-of-minds/{id}/
- railway_deployer uses RAILWAY_PROJECT_ID + RAILWAY_ENVIRONMENT_ID from env (not yet in .env)
- Pinecone filter syntax: `{"persona_id": pid}` (flat, not nested — SDK v8 quirk)
- voyageai + pinecone must be installed: `pip install voyageai pinecone-client`
