"""
config.py – Centralised settings loaded from environment / .env file.
All modules import from here; never read os.environ directly elsewhere.

FREE-TIER SETUP:
  LLM      → Groq  (free at console.groq.com)
  STT      → Whisper tiny  (runs locally, no API key)
  TTS      → gTTS  (free, uses Google Translate TTS)
  Memory   → FAISS (local, no API key)
  Email    → mock  (in-memory demo data)
  Calendar → mock  (in-memory demo data)
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── LLM Provider ─────────────────────────────────────────────────────────
    # llm_provider: "groq" (free) | "openai" (paid) | "mock" (no key, rule-based)
    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")

    # Groq – free at https://console.groq.com  (recommended)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama3-8b-8192", alias="GROQ_MODEL")

    # OpenAI – paid, only fill if you have a key
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Shared LLM settings
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")

    # ── Voice ─────────────────────────────────────────────────────────────────
    # whisper_model: "tiny" (fastest, ~39 MB) | "base" | "small" | "medium"
    whisper_model: str = Field(default="tiny", alias="WHISPER_MODEL")
    # tts_provider: "gtts" (free) | "elevenlabs" (paid)
    tts_provider: str = Field(default="gtts", alias="TTS_PROVIDER")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", alias="ELEVENLABS_VOICE_ID")

    # ── Memory ────────────────────────────────────────────────────────────────
    # vector_store: "simple" (no deps) | "faiss" | "chroma"
    vector_store: str = Field(default="simple", alias="VECTOR_STORE")
    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    faiss_index_path: str = Field(default="./data/faiss.index", alias="FAISS_INDEX_PATH")

    # ── Email ─────────────────────────────────────────────────────────────────
    # email_provider: "mock" (demo) | "smtp" (real, needs creds below)
    email_provider: str = Field(default="mock", alias="EMAIL_PROVIDER")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")

    # ── Calendar ──────────────────────────────────────────────────────────────
    # calendar_provider: "mock" (demo) | "google" (needs OAuth creds)
    calendar_provider: str = Field(default="mock", alias="CALENDAR_PROVIDER")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    audio_output_dir: str = Field(default="./data/audio", alias="AUDIO_OUTPUT_DIR")
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    max_audio_size_mb: int = Field(default=25, alias="MAX_AUDIO_SIZE_MB")

    model_config = {"env_file": ".env", "populate_by_name": True}

    # ── Derived helpers ───────────────────────────────────────────────────────

    @property
    def active_llm_model(self) -> str:
        """Return the model name for the active provider."""
        if self.llm_provider == "groq":
            return self.groq_model
        if self.llm_provider == "openai":
            return self.openai_model
        return "mock"

    @property
    def active_api_key(self) -> str:
        """Return the API key for the active provider."""
        if self.llm_provider == "groq":
            return self.groq_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return ""

    @property
    def use_llm(self) -> bool:
        """True if a real LLM provider is configured with a key."""
        return bool(self.active_api_key) and self.llm_provider != "mock"

    def ensure_dirs(self) -> None:
        """Create required data directories if they don't exist."""
        for d in [self.audio_output_dir, self.upload_dir,
                  self.chroma_persist_dir, "./data", "./logs"]:
            Path(d).mkdir(parents=True, exist_ok=True)


# Singleton – import this everywhere
settings = Settings()
settings.ensure_dirs()
