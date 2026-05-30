import json
import re
from pathlib import Path

from .base import BaseAgent
from ..config import settings


class PersonaIdentifierAgent(BaseAgent):
    name = "persona_identifier"
    description = "Validates persona ID, checks if it already exists in SQLite/Pinecone, returns known metadata"
    dependencies = []

    def run(self, persona_id: str, context: dict) -> dict:
        errors = []

        # Validate slug format
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", persona_id):
            raise ValueError(f"Invalid persona_id '{persona_id}' — must be lowercase kebab-case")

        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id
        persona_json_path = persona_dir / "persona.json"
        sources_json_path = persona_dir / "sources.json"

        # Load persona.json if it exists
        persona_meta = {}
        has_persona_json = persona_json_path.exists()
        if has_persona_json:
            with open(persona_json_path) as f:
                raw = json.load(f)
            meta = raw.get("metadata", raw)
            persona_meta = {
                "name": meta.get("name", persona_id),
                "hall": meta.get("hall_primary") or meta.get("hall", ""),
                "voice_id": meta.get("voice_id", ""),
                "dates": meta.get("dates", ""),
                "type": raw.get("type", "historical"),
            }
        else:
            errors.append("persona.json not found — create it before running the pipeline")

        # Check sources.json
        has_sources = sources_json_path.exists()
        source_count = 0
        if has_sources:
            with open(sources_json_path) as f:
                sources = json.load(f)
            source_count = len(sources.get("priority_1", [])) + len(sources.get("priority_2", []))

        # Check existing corpus files
        corpus_raw = persona_dir / "corpus" / "raw"
        corpus_cleaned = persona_dir / "corpus" / "cleaned"
        raw_count = len(list(corpus_raw.glob("*.*"))) if corpus_raw.exists() else 0
        cleaned_count = len(list(corpus_cleaned.glob("*.txt"))) if corpus_cleaned.exists() else 0

        # Check existing Pinecone vector count
        vector_count = 0
        pinecone_ok = False
        if settings.pinecone_api_key:
            try:
                from pinecone import Pinecone
                pc = Pinecone(api_key=settings.pinecone_api_key)
                index = pc.Index(settings.pinecone_index, host=settings.pinecone_host)
                stats = index.describe_index_stats()
                ns_key = persona_id.replace("-", "_")
                # Try both namespace formats
                for key in [ns_key, persona_id]:
                    ns = stats.get("namespaces", {}).get(key, {})
                    if ns:
                        vector_count = ns.get("vector_count", 0)
                        break
                if vector_count == 0:
                    # Fall back to filtered query count
                    result = index.query(
                        vector=[0.0] * 2048,
                        filter={"persona_id": persona_id},
                        top_k=1,
                    )
                    vector_count = result.get("total_count", 0)
                pinecone_ok = True
            except Exception as exc:
                errors.append(f"Pinecone check failed: {exc}")

        is_new = vector_count == 0 and cleaned_count == 0

        if errors and not has_persona_json:
            raise ValueError("; ".join(errors))

        return {
            "status": "ok",
            "persona_id": persona_id,
            "is_new": is_new,
            "has_persona_json": has_persona_json,
            "has_sources": has_sources,
            "source_count": source_count,
            "corpus_raw_files": raw_count,
            "corpus_cleaned_files": cleaned_count,
            "existing_vectors": vector_count,
            "pinecone_ok": pinecone_ok,
            "metadata": persona_meta,
            "warnings": errors,
        }
