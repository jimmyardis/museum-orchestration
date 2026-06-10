# ATLAS — museum-orchestration

## Meta
| Field | Value |
|---|---|
| Last Active | 2026-06-09 |
| Status | shipping |
| Repo | jimmyardis/museum-orchestration |
| Live | https://museum-orchestration-production.up.railway.app/dashboard |

## Current State
Agentic orchestration layer for the Museum of Minds persona pipeline: FastAPI + SQLite job system with 7 agents (persona_identifier → corpus_fetcher → corpus_cleaner → pinecone_uploader → page_generator → railway_deployer → tts_auditioner), SSE job streaming, retry with backoff, batch ingestion, and a live web dashboard. All 5 build phases complete and now deployed to Railway (service `museum-orchestration` in the `giving-expression` project).

## Next Action
Fix the empty-persona-inventory gap on Railway: the deployed service has MUSEUM_ROOT=/app but the repo contains no personas/ directory, so startup sync reports 0 personas (79 locally). Decide between bundling persona metadata into the repo, syncing from the jane-jacobs-bot GitHub repo, or treating Pinecone as the source of truth.

## Blockers
None. (Railway auth was the blocker; resolved 2026-06-09 with an account token stored as RAILWAY_API_TOKEN in ~/.env.)

## Open Questions
- Where should the deployed orchestrator read persona metadata from (repo bundle vs GitHub fetch vs Pinecone)?
- Should the GitHub repo be connected to the Railway GitHub App so pushes auto-deploy? (Currently manual redeploy only.)

## Session Log
### 2026-06-09
- Deployed to Railway after re-auth via account token (browserless login codes kept expiring; user supplied a token instead — now persisted in ~/.env as RAILWAY_API_TOKEN).
- deploy.sh needed two fixes in practice: `railway add` requires `--branch main` because the repo isn't connected to the Railway GitHub App, and the CLI's variable syntax is `--set k=v` (script's `set k=v` form didn't apply).
- Created service `museum-orchestration` in giving-expression, set all 15 env vars, generated public domain.
- Verified live: /status returns full agent registry, /dashboard renders (307 → /dashboard/ → 200).
- Found expected gap: /personas returns [] on Railway (no personas/ dir in the image). Documented fix options in PROGRESS.md; left unresolved.

### 2026-05-30 (retroactive)
- Completed Phases 1–5 of the build (core, agents, observability, dashboard, batch/retry). Deploy blocked on expired Railway OAuth.
