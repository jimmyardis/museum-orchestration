import base64
import json
from pathlib import Path

import requests

from .base import BaseAgent
from ..config import settings

GITHUB_API = "https://api.github.com"


class PageGeneratorAgent(BaseAgent):
    name = "page_generator"
    description = "Commits persona HTML page to jimmyardis/museum-of-minds via GitHub API"
    dependencies = ["pinecone_uploader"]

    def run(self, persona_id: str, context: dict) -> dict:
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN not set")

        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id

        # Prefer pre-built index.html, fall back to generating one
        html_path = persona_dir / "index.html"
        if not html_path.exists():
            # Look in museum-of-minds local clone if present
            local_museum = museum_root / "museum-of-minds" / persona_id / "index.html"
            if local_museum.exists():
                html_path = local_museum

        if html_path.exists():
            html_content = html_path.read_text(encoding="utf-8")
        else:
            # Generate minimal page from persona.json
            html_content = self._generate_html(persona_id, persona_dir)

        # Commit to museum-of-minds repo
        dest_path = f"{persona_id}/index.html"
        page_url = self._commit_to_github(
            repo=settings.museum_repo,
            path=dest_path,
            content=html_content,
            commit_msg=f"Add {persona_id} persona page",
        )

        return {
            "status": "ok",
            "page_url": page_url,
            "html_chars": len(html_content),
            "source": "existing" if html_path.exists() else "generated",
        }

    def _commit_to_github(self, repo: str, path: str, content: str, commit_msg: str) -> str:
        url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Check for existing file (need SHA for update)
        check = requests.get(url, headers=headers, timeout=30)
        sha = check.json().get("sha") if check.ok else None

        payload = {
            "message": commit_msg,
            "content": base64.b64encode(content.encode("utf-8")).decode(),
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")

        museum_domain = "museumofminds.com"
        return f"https://{museum_domain}/{path.split('/')[0]}/"

    def _generate_html(self, persona_id: str, persona_dir: Path) -> str:
        """Minimal persona page when no pre-built HTML exists."""
        persona_json_path = persona_dir / "persona.json"
        meta: dict = {}
        if persona_json_path.exists():
            with open(persona_json_path) as f:
                raw = json.load(f)
            meta = raw.get("metadata", raw)

        name = meta.get("name", persona_id.replace("-", " ").title())
        dates = meta.get("dates", "")
        tagline = meta.get("tagline", meta.get("description", ""))
        api_base = "https://museum-api-production-8ce6.up.railway.app"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} — Museum of Minds</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header>
    <a href="/" class="back-link">← Museum of Minds</a>
  </header>
  <main class="persona-page">
    <h1>{name}</h1>
    {f'<p class="dates">{dates}</p>' if dates else ''}
    {f'<p class="tagline">{tagline}</p>' if tagline else ''}
    <div id="chat-widget"
         data-persona="{persona_id}"
         data-api="{api_base}">
    </div>
  </main>
  <script src="/widget.js"></script>
</body>
</html>"""
