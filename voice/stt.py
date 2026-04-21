"""
voice/stt.py – Speech-to-Text using OpenAI Whisper (local model).
Accepts a path to an audio file and returns the transcribed text.
"""
from __future__ import annotations
import os
from pathlib import Path
from utils.logger import get_logger
from config import settings

logger = get_logger("voice.stt")


class SpeechToText:
    """Wraps Whisper for local audio transcription."""

    def __init__(self) -> None:
        self._model = None  # Lazy-loaded on first use

    def _load_model(self):
        """Load Whisper model (deferred to avoid startup cost)."""
        if self._model is None:
            try:
                import whisper
                logger.info(f"Loading Whisper model: {settings.whisper_model}")
                self._model = whisper.load_model(settings.whisper_model)
                logger.info("Whisper model loaded successfully")
            except ImportError:
                logger.warning("openai-whisper not installed; using mock STT")
                self._model = "mock"
        return self._model

    def transcribe(self, audio_path: str | Path) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to .wav / .mp3 / .m4a audio file

        Returns:
            Transcribed text string
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing: {audio_path.name}")
        model = self._load_model()

        if model == "mock":
            # Return a mock transcript for testing without GPU / model weights
            mock_text = "Schedule a meeting with the team tomorrow at 2 PM and send a confirmation email."
            logger.info(f"Mock transcript: {mock_text}")
            return mock_text

        result = model.transcribe(str(audio_path))
        transcript = result["text"].strip()
        logger.info(f"Transcript ({len(transcript)} chars): {transcript[:80]}…")
        return transcript


# Module-level singleton
stt = SpeechToText()
