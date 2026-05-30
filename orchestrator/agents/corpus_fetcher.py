from .base import BaseAgent


class CorpusFetcherAgent(BaseAgent):
    name = "corpus_fetcher"
    description = "Downloads corpus files from Archive.org, Gutenberg, and web; saves to local corpus/ directory"
    dependencies = ["persona_identifier"]

    def run(self, persona_id: str, context: dict) -> dict:
        # Phase 2: read personas/{persona_id}/sources.json, spawn sub-agents per source type
        # (archive_downloader, gutenberg_downloader, web_scraper), track download results
        # Returns {files_downloaded: [...], total_chars: N, errors: [...]}
        return {"status": "stub", "message": "Phase 2 implementation pending", "agent": self.name}
