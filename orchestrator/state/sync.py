"""
Pinecone → SQLite persona sync.

Strategy:
  1. Enumerate persona_ids from the local personas/ directory (always authoritative)
  2. Query Pinecone for per-persona vector counts (by sampling metadata)
  3. Upsert all into SQLite personas table
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .db import get_db

logger = logging.getLogger("sync")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_persona_meta(persona_dir: Path) -> dict:
    """Read name, hall, voice_id from persona.json. Returns {} on failure."""
    pj = persona_dir / "persona.json"
    if not pj.exists():
        return {}
    try:
        raw = json.loads(pj.read_text())
        meta = raw.get("metadata", raw)
        return {
            "name": meta.get("name", persona_dir.name),
            "hall": meta.get("hall_primary") or meta.get("hall", ""),
            "voice_id": meta.get("voice_id", ""),
        }
    except Exception:
        return {}


def _get_pinecone_counts(pc, index_name: str, host: str) -> dict[str, int]:
    """
    Returns {persona_id: vector_count} by sampling the Pinecone index.
    Uses describe_index_stats namespaces if available, otherwise samples metadata.
    """
    try:
        index = pc.Index(index_name, host=host)
        stats = index.describe_index_stats()
    except Exception as exc:
        logger.warning(f"Pinecone stats failed: {exc}")
        return {}

    namespaces = stats.get("namespaces", {})
    if namespaces:
        return {
            ns.replace("_", "-"): data.get("vector_count", 0)
            for ns, data in namespaces.items()
        }

    # Flat index — sample metadata to discover persona_ids and approximate counts
    counts: dict[str, int] = {}
    try:
        result = index.query(
            vector=[0.0] * 2048,
            top_k=100,
            include_metadata=True,
        )
        for match in result.get("matches", []):
            pid = match.get("metadata", {}).get("persona_id", "")
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
    except Exception as exc:
        logger.warning(f"Pinecone sample query failed: {exc}")

    return counts


def sync_from_pinecone() -> dict:
    """Pull all personas from local directory + Pinecone counts and upsert into SQLite."""
    from ..config import settings

    personas_dir = Path(settings.museum_root) / "personas"
    if not personas_dir.exists():
        return {"status": "error", "reason": f"personas/ dir not found at {personas_dir}"}

    # 1. Build persona list from local directory (authoritative source)
    local_personas: dict[str, dict] = {}
    for p in sorted(personas_dir.iterdir()):
        if not p.is_dir():
            continue
        meta = _load_persona_meta(p)
        if not meta and not (p / "sources.json").exists():
            continue  # skip non-persona dirs
        local_personas[p.name] = meta or {"name": p.name, "hall": "", "voice_id": ""}

    # 2. Get vector counts from Pinecone
    pinecone_counts: dict[str, int] = {}
    total_vectors = 0
    if settings.pinecone_api_key:
        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.pinecone_api_key)
            pinecone_counts = _get_pinecone_counts(pc, settings.pinecone_index, settings.pinecone_host)
            # Total from stats
            idx = pc.Index(settings.pinecone_index, host=settings.pinecone_host)
            total_vectors = idx.describe_index_stats().get("total_vector_count", 0)
        except Exception as exc:
            logger.warning(f"Pinecone connection failed: {exc}")

    # 3. Upsert into SQLite
    upserted = 0
    with get_db() as conn:
        for persona_id, meta in local_personas.items():
            vector_count = pinecone_counts.get(persona_id, 0)
            # If vector count is 0 but local corpus/cleaned exists, mark as needing embed
            cleaned_dir = personas_dir / persona_id / "corpus" / "cleaned"
            has_cleaned = cleaned_dir.exists() and any(cleaned_dir.glob("*.txt"))

            status = "complete" if vector_count > 0 else ("pending" if has_cleaned else "pending")

            conn.execute(
                """INSERT INTO personas (id, name, hall, status, vector_count, voice_id, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name,
                     hall=excluded.hall,
                     status=CASE WHEN personas.status IN ('building','failed') THEN personas.status
                                 ELSE excluded.status END,
                     vector_count=excluded.vector_count,
                     voice_id=excluded.voice_id,
                     last_updated=excluded.last_updated""",
                (persona_id, meta["name"], meta["hall"], status,
                 vector_count, meta["voice_id"], _now()),
            )
            upserted += 1

        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES ('last_pinecone_sync', ?, ?)",
            (_now(), _now()),
        )

    logger.info(f"Sync complete: {upserted} personas, {total_vectors} total vectors in Pinecone")
    return {
        "status": "ok",
        "personas_synced": upserted,
        "total_vectors": total_vectors,
        "synced_at": _now(),
    }
