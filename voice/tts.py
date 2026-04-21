"""
voice/tts.py – Text-to-Speech supporting gTTS and ElevenLabs.
Returns a path to the generated .mp3 audio file.
"""
from __future__ import annotations
import uuid
from pathlib import Path
from config import settings
from utils.logger import get_logger

logger = get_logger("voice.tts")


class TextToSpeech:
    """Converts text to speech audio and saves it to disk."""

    def __init__(self) -> None:
        self.output_dir = Path(settings.audio_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.provider = settings.tts_provider

    def _output_path(self, prefix: str = "tts") -> Path:
        return self.output_dir / f"{prefix}_{uuid.uuid4().hex[:8]}.mp3"

    # ── gTTS ─────────────────────────────────────────────────────────────────

    def _synthesize_gtts(self, text: str, output_path: Path) -> Path:
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(str(output_path))
            return output_path
        except ImportError:
            logger.warning("gTTS not installed; saving placeholder file")
            output_path.write_text(f"[TTS placeholder] {text}")
            return output_path

    # ── ElevenLabs ───────────────────────────────────────────────────────────

    def _synthesize_elevenlabs(self, text: str, output_path: Path) -> Path:
        import httpx
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
        headers = {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path

    # ── Public API ────────────────────────────────────────────────────────────

    def synthesize(self, text: str) -> Path:
        """
        Convert text to speech and return path to the audio file.

        Args:
            text: The string to speak

        Returns:
            Path object pointing to the .mp3 file
        """
        output_path = self._output_path()
        logger.info(f"TTS [{self.provider}]: '{text[:60]}…'")

        if self.provider == "elevenlabs" and settings.elevenlabs_api_key:
            return self._synthesize_elevenlabs(text, output_path)
        else:
            return self._synthesize_gtts(text, output_path)


# Module-level singleton
tts = TextToSpeech()
