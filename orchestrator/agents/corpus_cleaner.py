import re
from pathlib import Path

from .base import BaseAgent
from ..config import settings


def clean_text(text: str) -> str:
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
    text = re.sub(r"\n\s*-\s*\d+\s*-\s*\n", "\n", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r" +", " ", text)
    # Fix common OCR ligatures
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    # Normalize quotes
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    return text.strip()


class CorpusCleanerAgent(BaseAgent):
    name = "corpus_cleaner"
    description = "Cleans raw corpus text (OCR artifacts, whitespace) and saves to corpus/cleaned/"
    dependencies = ["corpus_fetcher"]

    def run(self, persona_id: str, context: dict) -> dict:
        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id
        raw_dir = persona_dir / "corpus" / "raw"
        cleaned_dir = persona_dir / "corpus" / "cleaned"
        cleaned_dir.mkdir(parents=True, exist_ok=True)

        if not raw_dir.exists():
            raise FileNotFoundError(f"corpus/raw/ not found at {raw_dir}")

        supported = {".txt", ".text"}
        files = [f for f in raw_dir.iterdir() if f.suffix.lower() in supported]

        if not files:
            # Try PDF extraction
            pdf_files = list(raw_dir.glob("*.pdf"))
            if pdf_files:
                files = pdf_files  # handled below
            else:
                raise FileNotFoundError(f"No .txt or .pdf files in {raw_dir}")

        results = {"cleaned": [], "failed": []}
        total_chars = 0

        for file_path in sorted(files):
            if file_path.name.startswith("_"):
                continue  # skip report files

            try:
                if file_path.suffix.lower() == ".pdf":
                    raw_text = self._extract_pdf(file_path)
                else:
                    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")

                if not raw_text or len(raw_text) < 200:
                    results["failed"].append({"file": file_path.name, "reason": "too short after read"})
                    continue

                cleaned = clean_text(raw_text)
                if len(cleaned) < 100:
                    results["failed"].append({"file": file_path.name, "reason": "too short after cleaning"})
                    continue

                out_path = cleaned_dir / (file_path.stem + ".txt")
                out_path.write_text(cleaned, encoding="utf-8")
                total_chars += len(cleaned)
                results["cleaned"].append({
                    "source": file_path.name,
                    "output": out_path.name,
                    "chars": len(cleaned),
                })
            except Exception as exc:
                results["failed"].append({"file": file_path.name, "reason": str(exc)})

        return {
            "status": "ok",
            "files_cleaned": len(results["cleaned"]),
            "files_failed": len(results["failed"]),
            "total_chars": total_chars,
            "details": results,
        }

    def _extract_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        reader = PdfReader(path)
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)
