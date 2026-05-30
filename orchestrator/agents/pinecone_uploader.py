import json
import time
import uuid
from pathlib import Path
from typing import Iterator

from .base import BaseAgent
from ..config import settings

CHUNK_TOKENS = 600
OVERLAP_TOKENS = 100
WORDS_PER_CHUNK = int(CHUNK_TOKENS / 1.3)
WORDS_OVERLAP = int(OVERLAP_TOKENS / 1.3)
VOYAGE_BATCH = 8
PINECONE_BATCH = 96


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        chunk = " ".join(words[start: start + WORDS_PER_CHUNK]).strip()
        if chunk:
            chunks.append(chunk)
        start += WORDS_PER_CHUNK - WORDS_OVERLAP
    return chunks


def _language_era(year: int) -> str:
    if year < 1700:  return "early_modern"
    if year < 1800:  return "enlightenment"
    if year < 1900:  return "19th_century"
    return "20th_century"


def _batched(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i: i + size]


class PineconeUploaderAgent(BaseAgent):
    name = "pinecone_uploader"
    description = "Embeds corpus chunks via Voyage AI voyage-3-large (2048-dim) and upserts to Pinecone"
    dependencies = ["corpus_cleaner"]

    def run(self, persona_id: str, context: dict) -> dict:
        if not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY not set")
        if not settings.pinecone_api_key:
            raise RuntimeError("PINECONE_API_KEY not set")

        import voyageai
        from pinecone import Pinecone

        vo = voyageai.Client(api_key=settings.voyage_api_key)
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index, host=settings.pinecone_host)

        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id
        cleaned_dir = persona_dir / "corpus" / "cleaned"
        raw_dir = persona_dir / "corpus" / "raw"
        sources_path = persona_dir / "sources.json"

        if not cleaned_dir.exists():
            raise FileNotFoundError(f"corpus/cleaned/ not found — run corpus_cleaner first")

        # Build source metadata lookup from sources.json
        source_meta: dict[str, dict] = {}
        if sources_path.exists():
            with open(sources_path) as f:
                sources = json.load(f)
            for tier in ("priority_1", "priority_2"):
                for entry in sources.get(tier, []):
                    stem_parts = []
                    t = entry.get("title", "")
                    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in t).replace(" ", "_")
                    source_meta[safe] = {
                        "work_title": t,
                        "author": entry.get("author", ""),
                        "year": entry.get("year", 0),
                        "source_tier": tier,
                    }

        txt_files = sorted(cleaned_dir.glob("*.txt"))
        if not txt_files:
            raise FileNotFoundError(f"No .txt files in {cleaned_dir}")

        all_chunks: list[dict] = []
        for txt_path in txt_files:
            if txt_path.name.startswith("_"):
                continue
            text = txt_path.read_text(encoding="utf-8", errors="ignore")
            chunks = _chunk_text(text)

            # Find metadata for this file
            meta = source_meta.get(txt_path.stem, {})
            # Try looking up per raw .json sidecar
            raw_meta_path = raw_dir / f"{txt_path.stem}.json"
            if raw_meta_path.exists():
                with open(raw_meta_path) as f:
                    raw_meta = json.load(f)
                meta = {
                    "work_title": raw_meta.get("title", txt_path.stem),
                    "author": raw_meta.get("author", ""),
                    "year": raw_meta.get("year", 0),
                    "source_tier": "priority_1",
                }

            year = int(meta.get("year", 0))
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "id": f"{persona_id}_{txt_path.stem}_{i}_{uuid.uuid4().hex[:8]}",
                    "text": chunk,
                    "metadata": {
                        "persona_id": persona_id,
                        "work_title": meta.get("work_title", txt_path.stem),
                        "author": meta.get("author", ""),
                        "year": str(year),
                        "decade": f"{year // 10 * 10}s" if year else "",
                        "language_era": _language_era(year) if year else "",
                        "source_tier": meta.get("source_tier", "priority_1"),
                        "chunk_index": i,
                        "collection_type": "corpus",
                        "text": chunk,
                    },
                })

        total_upserted = 0
        # Embed in VOYAGE_BATCH chunks, upsert in PINECONE_BATCH batches
        texts = [c["text"] for c in all_chunks]
        embeddings = []

        for text_batch in _batched(texts, VOYAGE_BATCH):
            result = vo.embed(text_batch, model="voyage-3-large")
            embeddings.extend(result.embeddings)
            time.sleep(0.1)  # rate limit headroom

        vectors = [
            {"id": c["id"], "values": emb, "metadata": c["metadata"]}
            for c, emb in zip(all_chunks, embeddings)
        ]

        for vec_batch in _batched(vectors, PINECONE_BATCH):
            index.upsert(vectors=vec_batch)
            total_upserted += len(vec_batch)

        return {
            "status": "ok",
            "files_processed": len(txt_files),
            "chunks_created": len(all_chunks),
            "vectors_upserted": total_upserted,
        }
