import uuid
import json
import traceback
from datetime import datetime, timezone

from ..state.db import get_db
from ..agents.registry import get_agent, PIPELINE_ORDER

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 45]  # exponential backoff seconds


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(persona_id: str, agents: list[str] | None = None) -> str:
    """Execute the persona build pipeline. Returns job batch ID."""
    if agents is None:
        agents = PIPELINE_ORDER

    batch_id = str(uuid.uuid4())
    context: dict = {"persona_id": persona_id, "batch_id": batch_id}

    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO personas (id, name, status) VALUES (?, ?, 'building')",
            (persona_id, persona_id),
        )
        conn.execute(
            "UPDATE personas SET status = 'building', last_updated = ? WHERE id = ?",
            (_now(), persona_id),
        )
        job_ids = {}
        for agent_name in agents:
            job_id = str(uuid.uuid4())
            job_ids[agent_name] = job_id
            conn.execute(
                """INSERT INTO jobs (id, persona_id, agent_name, status, created_at)
                   VALUES (?, ?, ?, 'queued', ?)""",
                (job_id, persona_id, agent_name, _now()),
            )

    for agent_name in agents:
        job_id = job_ids[agent_name]
        success = _run_agent_with_retry(agent_name, persona_id, context, job_id)
        if not success:
            with get_db() as conn:
                conn.execute(
                    "UPDATE personas SET status = 'failed', last_updated = ? WHERE id = ?",
                    (_now(), persona_id),
                )
            break
    else:
        with get_db() as conn:
            conn.execute(
                "UPDATE personas SET status = 'complete', last_updated = ? WHERE id = ?",
                (_now(), persona_id),
            )

    return batch_id


def _run_agent_with_retry(
    agent_name: str,
    persona_id: str,
    context: dict,
    job_id: str,
) -> bool:
    """Run agent with exponential backoff retry. Returns True on success."""
    import time

    for attempt in range(MAX_RETRIES):
        started = _now()
        with get_db() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (started, job_id),
            )
            conn.execute(
                "UPDATE agent_stats SET status = 'running', current_job_id = ? WHERE agent_name = ?",
                (job_id, agent_name),
            )

        try:
            agent = get_agent(agent_name)
            result = agent.run(persona_id, context)
            context[agent_name] = result

            completed = _now()
            with get_db() as conn:
                conn.execute(
                    """UPDATE jobs SET status = 'complete', completed_at = ?, output_json = ?
                       WHERE id = ?""",
                    (completed, json.dumps(result), job_id),
                )
                conn.execute(
                    """UPDATE agent_stats
                       SET status = 'idle', last_run = ?,
                           success_count = success_count + 1, current_job_id = NULL
                       WHERE agent_name = ?""",
                    (completed, agent_name),
                )
            return True

        except Exception as exc:
            tb = traceback.format_exc()
            is_last = attempt == MAX_RETRIES - 1
            status = "failed" if is_last else "queued"
            completed = _now()

            with get_db() as conn:
                conn.execute(
                    """UPDATE jobs SET status = ?, completed_at = ?, error_msg = ?
                       WHERE id = ?""",
                    (status, completed, f"[attempt {attempt+1}/{MAX_RETRIES}] {exc}", job_id),
                )
                conn.execute(
                    """UPDATE agent_stats
                       SET status = ?, last_run = ?,
                           failure_count = failure_count + 1, current_job_id = NULL
                       WHERE agent_name = ?""",
                    ("error" if is_last else "idle", completed, agent_name),
                )
                conn.execute(
                    """INSERT INTO error_log
                       (agent_name, persona_id, error_type, error_msg, stack_trace)
                       VALUES (?, ?, ?, ?, ?)""",
                    (agent_name, persona_id, type(exc).__name__, str(exc), tb),
                )

            if is_last:
                return False

            delay = RETRY_DELAYS[attempt]
            time.sleep(delay)

    return False


def run_batch(
    persona_ids: list[str],
    agents: list[str] | None = None,
) -> list[str]:
    """Queue pipeline for multiple personas. Returns list of batch IDs."""
    return [run_pipeline(pid, agents) for pid in persona_ids]
