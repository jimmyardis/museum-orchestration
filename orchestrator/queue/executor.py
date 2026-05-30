import uuid
import json
import traceback
from datetime import datetime, timezone

from ..state.db import get_db
from ..agents.registry import get_agent, PIPELINE_ORDER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(persona_id: str, agents: list[str] | None = None) -> str:
    """Execute the persona build pipeline. Returns job batch ID."""
    if agents is None:
        agents = PIPELINE_ORDER

    batch_id = str(uuid.uuid4())
    context: dict = {"persona_id": persona_id, "batch_id": batch_id}

    with get_db() as conn:
        # Ensure persona row exists
        conn.execute(
            "INSERT OR IGNORE INTO personas (id, name, status) VALUES (?, ?, 'building')",
            (persona_id, persona_id),
        )
        conn.execute(
            "UPDATE personas SET status = 'building', last_updated = ? WHERE id = ?",
            (_now(), persona_id),
        )

        # Pre-create all job rows so the queue is visible immediately
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
            context[agent_name] = result  # pass output downstream

            completed = _now()
            with get_db() as conn:
                conn.execute(
                    """UPDATE jobs SET status = 'complete', completed_at = ?, output_json = ?
                       WHERE id = ?""",
                    (completed, json.dumps(result), job_id),
                )
                conn.execute(
                    """UPDATE agent_stats
                       SET status = 'idle', last_run = ?, success_count = success_count + 1,
                           current_job_id = NULL
                       WHERE agent_name = ?""",
                    (completed, agent_name),
                )

        except Exception as exc:
            completed = _now()
            tb = traceback.format_exc()
            with get_db() as conn:
                conn.execute(
                    """UPDATE jobs SET status = 'failed', completed_at = ?, error_msg = ?
                       WHERE id = ?""",
                    (completed, str(exc), job_id),
                )
                conn.execute(
                    """UPDATE agent_stats
                       SET status = 'error', last_run = ?, failure_count = failure_count + 1,
                           current_job_id = NULL
                       WHERE agent_name = ?""",
                    (completed, agent_name),
                )
                conn.execute(
                    """INSERT INTO error_log (agent_name, persona_id, error_type, error_msg, stack_trace)
                       VALUES (?, ?, ?, ?, ?)""",
                    (agent_name, persona_id, type(exc).__name__, str(exc), tb),
                )
                conn.execute(
                    "UPDATE personas SET status = 'failed', last_updated = ? WHERE id = ?",
                    (completed, persona_id),
                )
            break  # stop pipeline on failure
    else:
        # All agents completed successfully
        with get_db() as conn:
            conn.execute(
                "UPDATE personas SET status = 'complete', last_updated = ? WHERE id = ?",
                (_now(), persona_id),
            )

    return batch_id
