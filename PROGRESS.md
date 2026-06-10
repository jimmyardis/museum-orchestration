# Museum Orchestration Build Progress

## Current Phase: COMPLETE (all 5 phases)
## Last Session: 2026-06-09
## Status: DEPLOYED — live on Railway

## Completed

### Phase 1: Orchestration Core ✅
- FastAPI app, CORS, lifespan DB init
- 5-table SQLite schema + context manager (WAL mode, FK enforcement)
- Pydantic models, BaseAgent ABC, 7 agents in registry, PIPELINE_ORDER
- Full working job executor, 10 REST endpoints

### Phase 2: Agent Integration ✅
- All 7 agents fully implemented (persona_identifier, corpus_fetcher, corpus_cleaner,
  pinecone_uploader, page_generator, railway_deployer, tts_auditioner)
- Config expanded with all Railway/GitHub/Voyage credentials
- .env populated with all credentials

### Phase 3: Memory and Observability ✅
- Startup Pinecone sync (enumerates local personas/ directory as authoritative source)
- SSE job streaming at GET /jobs/{id}/stream
- Real POST /sync background task + GET /sync/status
- GET /errors endpoint; enhanced /status with success rates + error counts
- Verified: 79 personas, 146,164 Pinecone vectors at startup

### Phase 4: Web Dashboard ✅
- dashboard/index.html served at /dashboard (no build step)
- Live 10s polling: personas, agent status, jobs, errors
- Persona table with search + status filter + per-row pipeline trigger
- Agent success rate table; recent jobs; error log; manual sync button

### Phase 5: Advanced Features ✅
- **Retry logic** — exponential backoff (5s/15s/45s, max 3 attempts) in executor
- **POST /batch** — batch ingestion: `{persona_ids: [...], agents: [...]}` queues N pipelines
- **POST /personas** — add new persona to DB (with optional immediate pipeline trigger)
- **Batch run form** in dashboard — comma-separated persona IDs → batch trigger
- **Add persona form** in dashboard — ID + name + hall + run pipeline checkbox
- **deploy.sh** — one-command Railway deploy after `railway login`

## Railway Deploy ✅ (2026-06-09)

Deployed via account token (stored as RAILWAY_API_TOKEN in ~/.env).
- Service: `museum-orchestration` in `giving-expression` project, repo jimmyardis/museum-orchestration branch main
- Note: repo is NOT connected to the Railway GitHub App — pushes do not auto-deploy.
  Redeploy with: `railway up --service museum-orchestration --detach` (or redeploy from dashboard)
- deploy.sh needed `--branch main` on `railway add` (GitHub App not connected); var syntax is `--set k=v`

Dashboard live at: https://museum-orchestration-production.up.railway.app/dashboard

### Known gap: 0 personas on Railway
MUSEUM_ROOT=/app but the repo contains no personas/ directory, so startup sync
finds 0 personas (locally it found 79). Fix options: bundle persona.json metadata
into the repo, sync from GitHub (jane-jacobs-bot repo), or point sync at Pinecone
as the source of truth. Until then the dashboard works but the persona table is empty.

## Known Notes
- Pinecone index is flat (no namespaces) — per-persona vector counts tracked at 0 in SQLite
  (full per-persona count would need 79 filter queries; not worth the API cost at sync time)
- MUSEUM_ROOT on Railway should be set to wherever the personas/ dir is mounted
  (the orchestrator needs read access to personas/ for persona.json + sources.json)
- Railway deploy: service uses jimmyardis/museum-orchestration repo (not jane-jacobs-bot)
