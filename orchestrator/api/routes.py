import json
import time
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from ..state.db import get_db
from ..state.models import TriggerRequest, TriggerResponse, BatchRequest, BatchResponse, PersonaAddRequest
from ..state.sync import sync_from_pinecone
from ..agents.registry import PIPELINE_ORDER, list_agents
from ..queue.executor import run_pipeline, run_batch

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ #
#  Health & Status                                                     #
# ------------------------------------------------------------------ #

@router.get("/health")
def health():
    try:
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        db_ok = True
    except Exception:
        db_ok, count = False, 0
    return {"status": "ok" if db_ok else "degraded", "db_ok": db_ok, "persona_count": count, "timestamp": _now()}


@router.get("/status")
def status():
    with get_db() as conn:
        persona_counts = {
            row["status"]: row["cnt"]
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt FROM personas GROUP BY status"
            ).fetchall()
        }
        agent_stats = [dict(r) for r in conn.execute("SELECT * FROM agent_stats").fetchall()]
        recent_jobs = [dict(r) for r in conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
        total = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        complete = conn.execute("SELECT COUNT(*) FROM personas WHERE status='complete'").fetchone()[0]
        total_vectors = conn.execute(
            "SELECT COALESCE(SUM(vector_count),0) FROM personas"
        ).fetchone()[0]
        last_sync = conn.execute(
            "SELECT value FROM system_state WHERE key='last_pinecone_sync'"
        ).fetchone()

        # Agent success rates
        for a in agent_stats:
            total_runs = a["success_count"] + a["failure_count"]
            a["success_rate"] = round(a["success_count"] / total_runs * 100, 1) if total_runs else None

        # Error counts last 24h
        error_count = conn.execute(
            "SELECT COUNT(*) FROM error_log WHERE timestamp > datetime('now','-1 day')"
        ).fetchone()[0]

    return {
        "projectHealth": {
            "targetPersonas": 500,
            "currentPersonas": total,
            "completedPersonas": complete,
            "completionPercent": round(complete / 500 * 100, 1),
            "totalVectors": total_vectors,
            "lastPineconeSync": last_sync["value"] if last_sync else None,
        },
        "personasByStatus": persona_counts,
        "agents": agent_stats,
        "recentJobs": recent_jobs,
        "errorsLast24h": error_count,
    }


# ------------------------------------------------------------------ #
#  Personas                                                            #
# ------------------------------------------------------------------ #

@router.get("/personas")
def list_personas(hall: str = None, status: str = None):
    query = "SELECT * FROM personas"
    params = []
    filters = []
    if hall:
        filters.append("hall = ?")
        params.append(hall)
    if status:
        filters.append("status = ?")
        params.append(status)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY name ASC"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/personas/{persona_id}")
def get_persona(persona_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
        jobs = conn.execute(
            "SELECT * FROM jobs WHERE persona_id = ? ORDER BY created_at DESC LIMIT 20",
            (persona_id,),
        ).fetchall()
    return {"persona": dict(row), "jobs": [dict(j) for j in jobs]}


@router.post("/personas/{persona_id}/trigger", response_model=TriggerResponse)
def trigger_pipeline(persona_id: str, req: TriggerRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline, persona_id, PIPELINE_ORDER)
    return TriggerResponse(
        job_batch_id="queued",
        persona_id=persona_id,
        agents=PIPELINE_ORDER,
        message=f"Full pipeline queued for '{persona_id}' ({len(PIPELINE_ORDER)} agents).",
    )


@router.post("/personas/{persona_id}/trigger/{agent_name}", response_model=TriggerResponse)
def trigger_agent(persona_id: str, agent_name: str, background_tasks: BackgroundTasks):
    known = {a["name"] for a in list_agents()}
    if agent_name not in known:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
    background_tasks.add_task(run_pipeline, persona_id, [agent_name])
    return TriggerResponse(
        job_batch_id="queued",
        persona_id=persona_id,
        agents=[agent_name],
        message=f"Agent '{agent_name}' queued for '{persona_id}'.",
    )


# ------------------------------------------------------------------ #
#  Jobs                                                                #
# ------------------------------------------------------------------ #

@router.get("/jobs")
def list_jobs(limit: int = 50, persona_id: str = None, status: str = None):
    query = "SELECT * FROM jobs"
    params = []
    filters = []
    if persona_id:
        filters.append("persona_id = ?")
        params.append(persona_id)
    if status:
        filters.append("status = ?")
        params.append(status)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return dict(row)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """Server-sent events stream for real-time job progress."""
    async def event_generator():
        last_status = None
        poll_count = 0
        while poll_count < 600:  # max ~5 minutes
            await asyncio.sleep(0.5)
            poll_count += 1
            with get_db() as conn:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                yield f"event: error\ndata: {json.dumps({'error': 'job not found'})}\n\n"
                break
            job = dict(row)
            if job["status"] != last_status:
                last_status = job["status"]
                yield f"event: update\ndata: {json.dumps(job)}\n\n"
            if job["status"] in ("complete", "failed"):
                yield f"event: done\ndata: {json.dumps(job)}\n\n"
                break
        else:
            yield f"event: timeout\ndata: {json.dumps({'message': 'stream timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------ #
#  Memory, Agents, Sync, Errors                                        #
# ------------------------------------------------------------------ #

@router.get("/memory")
def get_memory():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        complete = conn.execute("SELECT COUNT(*) FROM personas WHERE status='complete'").fetchone()[0]
        agent_rows = conn.execute("SELECT * FROM agent_stats").fetchall()

    feature_map = {
        "persona_identifier": "stable",
        "corpus_fetcher": "stable",
        "corpus_cleaner": "stable",
        "pinecone_uploader": "stable",
        "page_generator": "stable",
        "railway_deployer": "stable",
        "tts_auditioner": "stable",
        "orchestration_core": "stable",
        "pinecone_sync": "stable",
        "job_sse_streaming": "stable",
        "orchestration_ui": "stable",
    }

    return {
        "projectHealth": {
            "targetPersonas": 500,
            "currentPersonas": total,
            "completedPersonas": complete,
            "completionPercent": round(complete / 500 * 100, 1),
            "lastSync": _now(),
        },
        "featureMap": feature_map,
        "agents": {r["agent_name"]: dict(r) for r in agent_rows},
    }


@router.get("/agents")
def list_agents_endpoint():
    return list_agents()


# ------------------------------------------------------------------ #
#  Batch ingestion                                                     #
# ------------------------------------------------------------------ #

@router.post("/batch", response_model=BatchResponse)
def batch_trigger(req: BatchRequest, background_tasks: BackgroundTasks):
    agents = req.agents or PIPELINE_ORDER
    if not req.persona_ids:
        raise HTTPException(status_code=422, detail="persona_ids must not be empty")
    background_tasks.add_task(run_batch, req.persona_ids, agents)
    return BatchResponse(
        queued=len(req.persona_ids),
        persona_ids=req.persona_ids,
        agents=agents,
        message=f"{len(req.persona_ids)} persona pipelines queued ({len(agents)} agents each).",
    )


# ------------------------------------------------------------------ #
#  Add persona manually                                                #
# ------------------------------------------------------------------ #

@router.post("/personas")
def add_persona(req: PersonaAddRequest, background_tasks: BackgroundTasks):
    import re
    if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", req.persona_id):
        raise HTTPException(status_code=422, detail="persona_id must be lowercase kebab-case")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM personas WHERE id = ?", (req.persona_id,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Persona '{req.persona_id}' already exists"
            )
        conn.execute(
            """INSERT INTO personas (id, name, hall, status, vector_count, voice_id, last_updated)
               VALUES (?, ?, ?, 'pending', 0, ?, ?)""",
            (req.persona_id, req.name, req.hall, req.voice_id, _now()),
        )

    if req.run_pipeline:
        background_tasks.add_task(run_pipeline, req.persona_id, PIPELINE_ORDER)

    return {
        "persona_id": req.persona_id,
        "name": req.name,
        "hall": req.hall,
        "pipeline_queued": req.run_pipeline,
        "message": f"Persona '{req.persona_id}' added."
        + (" Pipeline queued." if req.run_pipeline else ""),
    }


@router.post("/sync")
def sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_from_pinecone)
    return {"message": "Pinecone sync started in background. Check /status for results."}


@router.get("/sync/status")
def sync_status():
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM system_state WHERE key='last_pinecone_sync'"
        ).fetchone()
    return {"last_pinecone_sync": row["value"] if row else None}


@router.get("/errors")
def list_errors(limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM error_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
