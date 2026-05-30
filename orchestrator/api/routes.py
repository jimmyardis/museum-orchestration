import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..state.db import get_db
from ..state.models import TriggerRequest, TriggerResponse
from ..agents.registry import PIPELINE_ORDER, list_agents
from ..queue.executor import run_pipeline

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/health")
def health():
    try:
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        db_ok = True
    except Exception as exc:
        db_ok = False
        count = 0
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
        recent_jobs = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        ]
        total = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]

    return {
        "projectHealth": {
            "targetPersonas": 500,
            "currentPersonas": total,
            "completionPercent": round(total / 500 * 100, 1),
            "lastSync": _now(),
        },
        "personasByStatus": persona_counts,
        "agents": agent_stats,
        "recentJobs": recent_jobs,
    }


@router.get("/personas")
def list_personas():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM personas ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@router.get("/personas/{persona_id}")
def get_persona(persona_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
        jobs = conn.execute(
            "SELECT * FROM jobs WHERE persona_id = ? ORDER BY created_at DESC", (persona_id,)
        ).fetchall()
    return {"persona": dict(row), "jobs": [dict(j) for j in jobs]}


@router.post("/personas/{persona_id}/trigger", response_model=TriggerResponse)
def trigger_pipeline(persona_id: str, req: TriggerRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline, persona_id, PIPELINE_ORDER)
    return TriggerResponse(
        job_batch_id="queued",
        persona_id=persona_id,
        agents=PIPELINE_ORDER,
        message=f"Pipeline queued for '{persona_id}'. All {len(PIPELINE_ORDER)} agents will run in order.",
    )


@router.post("/personas/{persona_id}/trigger/{agent_name}", response_model=TriggerResponse)
def trigger_agent(persona_id: str, agent_name: str, background_tasks: BackgroundTasks):
    if agent_name not in {a["name"] for a in list_agents()}:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
    background_tasks.add_task(run_pipeline, persona_id, [agent_name])
    return TriggerResponse(
        job_batch_id="queued",
        persona_id=persona_id,
        agents=[agent_name],
        message=f"Agent '{agent_name}' queued for '{persona_id}'.",
    )


@router.get("/jobs")
def list_jobs():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return dict(row)


@router.get("/memory")
def get_memory():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
        complete = conn.execute(
            "SELECT COUNT(*) FROM personas WHERE status = 'complete'"
        ).fetchone()[0]
        agent_rows = conn.execute("SELECT * FROM agent_stats").fetchall()

    feature_map = {
        "persona_identifier": "stub",
        "corpus_fetcher": "stub",
        "corpus_cleaner": "stub",
        "pinecone_uploader": "stub",
        "page_generator": "stub",
        "railway_deployer": "stub",
        "tts_auditioner": "stub",
        "orchestration_core": "stable",
        "orchestration_ui": "planned",
    }

    return {
        "projectHealth": {
            "targetPersonas": 500,
            "currentPersonas": total,
            "completionPercent": round(total / 500 * 100, 1),
            "lastSync": _now(),
        },
        "featureMap": feature_map,
        "agents": {r["agent_name"]: dict(r) for r in agent_rows},
    }


@router.get("/agents")
def list_agents_endpoint():
    return list_agents()


@router.post("/sync")
def sync():
    return {"message": "Pinecone sync not yet implemented (Phase 3)"}
