# Museum Orchestration Build Progress

## Current Phase: 5
## Last Session: 2026-05-30
## Status: in-progress

## Completed

### Phase 1: Orchestration Core ✅
- FastAPI app, CORS, lifespan DB init
- 5-table SQLite schema + context manager (WAL mode, FK enforcement)
- Pydantic models (Persona, Job, AgentStats, Trigger*)
- BaseAgent ABC + 7 agents in registry with PIPELINE_ORDER
- Full working job executor with state tracking, error logging, pipeline control
- 10 REST endpoints

### Phase 2: Agent Integration ✅
- **persona_identifier** — validates slug, reads persona.json, checks Pinecone
- **corpus_fetcher** — Archive.org (direct id + search) + Gutenberg (3 URL patterns)
- **corpus_cleaner** — OCR cleanup, whitespace normalization, PDF extraction
- **pinecone_uploader** — Voyage AI voyage-3-large (2048-dim), 600t/100t chunks, batched upsert
- **page_generator** — GitHub API commit to jimmyardis/museum-of-minds
- **railway_deployer** — Railway GraphQL: create service, connect repo, domain, env vars, deploy
- **tts_auditioner** — ElevenLabs preview clips
- Config expanded with all Railway/GitHub/Voyage credentials; .env populated

### Phase 3: Memory and Observability ✅
- `state/sync.py` — Pinecone + local directory sync on startup
  - Always enumerates personas/ directory as authoritative source
  - Gets total vector count from Pinecone describe_index_stats()
  - Upserts all personas into SQLite with name/hall/voice metadata
- Startup sync runs on every boot; 79 personas + 146k vectors confirmed live
- Real `/sync` POST endpoint (background task)
- `/sync/status` GET endpoint
- `/errors` GET endpoint with 24h filter on /status
- SSE job streaming at `GET /jobs/{job_id}/stream`
- Enhanced `/status` — agent success rates, errors-last-24h, total vectors, last sync timestamp
- `/personas` accepts `?hall=` and `?status=` filters
- `/jobs` accepts `?persona_id=` and `?status=` filters

### Phase 4: Web Dashboard ✅
- `dashboard/index.html` — single-file dashboard served at `/dashboard`
- Live polling every 10s (no build step, no npm, deploys with the FastAPI service)
- Overview cards: total personas, completed, vector count, errors/24h + progress bar
- Personas table with search, status filter, and per-persona "▶ Run" pipeline trigger
- Agent status table with success rate, run count, last-run time
- Recent jobs live view
- Error log with timestamps
- Manual "↺ Sync Pinecone" button

## Next Session: Phase 5 — Advanced Features

1. **Batch ingestion endpoint** — `POST /batch` body: `{personas: [...], agents: [...]}` — queues N pipelines
2. **Persona add form** in dashboard — input field for new persona_id + hall, triggers identification
3. **Auto-scheduling rules** — cron-like table in SQLite; background task checks and fires pipelines
4. **Retry logic** — exponential backoff for failed agents (max 3 attempts)
5. **Railway deploy to production** — add this service to giving-expression project

## Notes
- Pinecone index is flat (no namespaces) — per-persona vector counts show as 0 in SQLite
  (all 146k vectors are under one namespace; would need per-persona filter queries to count)
- Dashboard API_BASE auto-detects from window.location.origin — works locally and on Railway
- .env is populated with all credentials; .env excluded from git
- Railway PROJECT_ID=2bf7b805, ENVIRONMENT_ID=4af3086a
