import json
import requests
from pathlib import Path

from .base import BaseAgent
from ..config import settings

ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
ARCHIVE_META   = "https://archive.org/metadata/"
ARCHIVE_DL     = "https://archive.org/download/"

GUTENBERG_PATTERNS = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://www.gutenberg.org/files/{id}/{id}-0.txt",
    "https://www.gutenberg.org/files/{id}/{id}.txt",
]


class CorpusFetcherAgent(BaseAgent):
    name = "corpus_fetcher"
    description = "Downloads corpus files from Archive.org and Gutenberg based on sources.json"
    dependencies = ["persona_identifier"]

    def run(self, persona_id: str, context: dict) -> dict:
        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id
        sources_path = persona_dir / "sources.json"

        if not sources_path.exists():
            raise FileNotFoundError(f"sources.json not found at {sources_path}")

        with open(sources_path) as f:
            sources = json.load(f)

        raw_dir = persona_dir / "corpus" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        all_sources = sources.get("priority_1", []) + sources.get("priority_2", [])
        results = {"downloaded": [], "skipped": [], "failed": []}

        for entry in all_sources:
            source_type = entry.get("source", "archive")
            title = entry.get("title", "unknown")

            if source_type == "gutenberg" or entry.get("gutenberg_id"):
                ok, path = self._fetch_gutenberg(entry, raw_dir)
            elif source_type == "archive" or entry.get("archive_identifier") or entry.get("search_terms"):
                ok, path = self._fetch_archive(entry, raw_dir)
            else:
                self.logger.info(f"Skipping '{title}' — source type '{source_type}' not auto-fetchable")
                results["skipped"].append({"title": title, "reason": f"source type: {source_type}"})
                continue

            if ok:
                results["downloaded"].append({"title": title, "path": str(path)})
            else:
                results["failed"].append({"title": title, "error": path})

        total_chars = sum(
            p.stat().st_size for item in results["downloaded"]
            if (p := Path(item["path"])).exists()
        )

        return {
            "status": "ok",
            "files_downloaded": len(results["downloaded"]),
            "files_skipped": len(results["skipped"]),
            "files_failed": len(results["failed"]),
            "total_chars": total_chars,
            "details": results,
        }

    # ------------------------------------------------------------------ #
    #  Archive.org                                                         #
    # ------------------------------------------------------------------ #

    def _fetch_archive(self, entry: dict, raw_dir: Path) -> tuple[bool, str]:
        title = entry.get("title", "unknown")
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).replace(" ", "_")
        year = entry.get("year", 0)

        if entry.get("archive_identifier"):
            identifier = entry["archive_identifier"]
        elif entry.get("search_terms"):
            identifier = self._search_archive(entry["search_terms"])
            if not identifier:
                return False, f"No Archive.org result for: {entry['search_terms']}"
        else:
            return False, "No archive_identifier or search_terms"

        meta = self._get_archive_meta(identifier)
        if not meta:
            return False, f"Could not fetch metadata for {identifier}"

        filename = self._find_best_text_file(meta)
        if not filename:
            return False, f"No downloadable text file for {identifier}"

        ext = filename.rsplit(".", 1)[-1]
        out_path = raw_dir / f"{safe_title}_{year}.{ext}"
        if out_path.exists():
            return True, str(out_path)

        try:
            url = f"{ARCHIVE_DL}{identifier}/{filename}"
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            self._save_meta_json(out_path, entry, identifier)
            return True, str(out_path)
        except Exception as exc:
            return False, str(exc)

    def _search_archive(self, terms: str) -> str | None:
        try:
            r = requests.get(ARCHIVE_SEARCH, params={
                "q": terms, "output": "json", "rows": 5,
                "fl[]": ["identifier", "title", "year", "mediatype"],
            }, timeout=30)
            r.raise_for_status()
            docs = r.json().get("response", {}).get("docs", [])
            return docs[0]["identifier"] if docs else None
        except Exception:
            return None

    def _get_archive_meta(self, identifier: str) -> dict | None:
        try:
            r = requests.get(f"{ARCHIVE_META}{identifier}", timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def _find_best_text_file(self, meta: dict) -> str | None:
        names = [f.get("name", "") for f in meta.get("files", [])]
        for name in names:
            if name.endswith("_djvu.txt"):
                return name
        for ext in ("txt", "pdf"):
            for name in names:
                if name.endswith(f".{ext}"):
                    return name
        return None

    # ------------------------------------------------------------------ #
    #  Gutenberg                                                           #
    # ------------------------------------------------------------------ #

    def _fetch_gutenberg(self, entry: dict, raw_dir: Path) -> tuple[bool, str]:
        gid = entry.get("gutenberg_id")
        title = entry.get("title", "unknown")
        year = entry.get("year", 0)
        if not gid:
            return False, "Missing gutenberg_id"

        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).replace(" ", "_")
        out_path = raw_dir / f"{safe_title}_{year}.txt"
        if out_path.exists():
            return True, str(out_path)

        for pattern in GUTENBERG_PATTERNS:
            url = pattern.format(id=gid)
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200 and len(r.text) > 5000:
                    out_path.write_text(r.text, encoding="utf-8")
                    self._save_meta_json(out_path, entry, str(gid))
                    return True, str(out_path)
            except Exception:
                continue

        return False, f"All Gutenberg URL patterns failed for ID {gid}"

    def _save_meta_json(self, file_path: Path, entry: dict, source_id: str):
        meta_path = file_path.with_suffix(".json")
        with open(meta_path, "w") as f:
            json.dump({
                "title": entry.get("title"),
                "author": entry.get("author"),
                "year": entry.get("year"),
                "source_id": source_id,
            }, f, indent=2)
