"""
voice/pipeline.py – End-to-end voice pipeline.
audio → transcript → agent → response text → audio
"""
from __future__ import annotations
from pathlib import Path
from voice.stt import stt
from voice.tts import tts
from utils.logger import get_logger

logger = get_logger("voice.pipeline")


class VoicePipeline:
    """
    Orchestrates the full voice round-trip:
      1. STT: audio file → transcript string
      2. (Agent processing happens outside this class)
      3. TTS: response string → audio file path
    """

    def audio_to_text(self, audio_path: str | Path) -> str:
        """Transcribe audio to text."""
        logger.info("Pipeline: audio → text")
        return stt.transcribe(audio_path)

    def text_to_audio(self, text: str) -> Path:
        """Synthesize text to audio and return file path."""
        logger.info("Pipeline: text → audio")
        return tts.synthesize(text)

    def full_pipeline(
        self, audio_path: str | Path, agent_fn
    ) -> tuple[str, Path]:
        """
        Run the complete voice pipeline.

        Args:
            audio_path: Input audio file
            agent_fn:   Callable(transcript: str) → response: str

        Returns:
            (response_text, response_audio_path)
        """
        transcript = self.audio_to_text(audio_path)
        logger.info(f"Transcript: {transcript}")

        response_text = agent_fn(transcript)
        logger.info(f"Agent response: {response_text[:100]}")

        audio_out = self.text_to_audio(response_text)
        return response_text, audio_out


# Module-level singleton
voice_pipeline = VoicePipeline()
