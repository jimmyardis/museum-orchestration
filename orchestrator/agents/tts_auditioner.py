import json
import tempfile
from pathlib import Path

import requests

from .base import BaseAgent
from ..config import settings

ELEVENLABS_TTS = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# Candidate voices to audition if persona has no voice_id yet
DEFAULT_CANDIDATE_VOICES = [
    {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George"},
    {"voice_id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel"},
    {"voice_id": "pqHfZKP75CvOlQylNhV4", "name": "Bill"},
    {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh"},
    {"voice_id": "ThT5KcBeYPX3keUQqHPh", "name": "Dorothy"},
]


class TTSAuditionerAgent(BaseAgent):
    name = "tts_auditioner"
    description = "Generates ElevenLabs voice preview clips for audition (optional — voice selection stays manual)"
    dependencies = ["persona_identifier"]

    def run(self, persona_id: str, context: dict) -> dict:
        if not settings.elevenlabs_api_key:
            return {
                "status": "skipped",
                "reason": "ELEVENLABS_API_KEY not set",
                "clips": [],
            }

        museum_root = Path(settings.museum_root)
        persona_dir = museum_root / "personas" / persona_id
        persona_json_path = persona_dir / "persona.json"

        sample_text = f"Good day. I am {persona_id.replace('-', ' ').title()}. I have much to say about the world."
        candidates = DEFAULT_CANDIDATE_VOICES[:]

        # If persona.json has a voice_id, audition only that one
        if persona_json_path.exists():
            with open(persona_json_path) as f:
                raw = json.load(f)
            meta = raw.get("metadata", raw)
            voice_id = meta.get("voice_id", "")
            sample_text = meta.get("sample_quote", sample_text)
            if voice_id:
                candidates = [{"voice_id": voice_id, "name": "configured"}]

        clips = []
        out_dir = Path(tempfile.mkdtemp(prefix=f"tts_{persona_id}_"))

        for candidate in candidates:
            vid = candidate["voice_id"]
            name = candidate["name"]
            out_path = out_dir / f"{persona_id}_{name}.mp3"

            try:
                resp = requests.post(
                    ELEVENLABS_TTS.format(voice_id=vid),
                    headers={
                        "xi-api-key": settings.elevenlabs_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": sample_text,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
                clips.append({"voice_id": vid, "name": name, "path": str(out_path)})
            except Exception as exc:
                self.logger.warning(f"TTS clip failed for voice {vid}: {exc}")

        return {
            "status": "ok",
            "clips": clips,
            "output_dir": str(out_dir),
            "note": "Listen to clips and update voice_id in persona.json manually",
        }
