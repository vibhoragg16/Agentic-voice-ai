"""
api/routes.py – FastAPI route definitions.
Endpoints: /voice-input, /process-task, /get-response, /confirm, /health
"""
from __future__ import annotations
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from agents.core import agent_core
from voice.pipeline import voice_pipeline
from voice.tts import tts
from config import settings
from utils.logger import get_logger
from utils.models import (
    ConfirmActionRequest,
    GetResponseResponse,
    ProcessTaskResponse,
    TaskStatus,
    VoiceInputResponse,
)

logger = get_logger("api.routes")
router = APIRouter()

# ─── In-memory transcript store (maps task_id → transcript) ──────────────────
_transcripts: dict[str, str] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health():
    """Quick liveness check."""
    return {"status": "ok", "env": settings.app_env}


# ─────────────────────────────────────────────────────────────────────────────
# Voice input  →  transcript
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/voice-input", response_model=VoiceInputResponse, tags=["Voice"])
async def voice_input(audio: UploadFile = File(...)):
    """
    Accept an audio file, transcribe it with Whisper, return the transcript.
    The caller should then POST to /process-task with the returned task_id.
    """
    # Validate file size
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    content = await audio.read()
    if len(content) > max_bytes:
        raise HTTPException(413, f"Audio file exceeds {settings.max_audio_size_mb} MB limit.")

    # Save to upload dir
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    task_id = str(uuid.uuid4())
    upload_path = Path(settings.upload_dir) / f"{task_id}{suffix}"
    upload_path.write_bytes(content)

    # Transcribe
    try:
        transcript = voice_pipeline.audio_to_text(upload_path)
    except Exception as e:
        logger.error(f"STT failed: {e}")
        raise HTTPException(500, f"Transcription failed: {e}")

    _transcripts[task_id] = transcript
    logger.info(f"Voice input task_id={task_id}: '{transcript[:80]}'")

    return VoiceInputResponse(
        transcript=transcript,
        task_id=task_id,
        status=TaskStatus.PENDING,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Process task  →  plan
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/process-task", response_model=ProcessTaskResponse, tags=["Agent"])
async def process_task(task_id: str = Form(...), text_input: str = Form(default="")):
    """
    Create a task plan from a transcript (voice) or plain text.
    Pass the task_id from /voice-input, or any new task_id with text_input.
    """
    # Resolve user request: prefer stored transcript, fall back to text_input
    user_request = _transcripts.get(task_id) or text_input
    if not user_request:
        raise HTTPException(400, "No transcript or text_input provided.")

    try:
        response = agent_core.process(user_request, task_id=task_id)
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        raise HTTPException(500, f"Planning error: {e}")

    return response


# ─────────────────────────────────────────────────────────────────────────────
# Get response  →  execute + voice output
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/get-response", response_model=GetResponseResponse, tags=["Agent"])
async def get_response(task_id: str = Form(...)):
    """
    Execute the planned task and return text + audio URL.
    If any steps are still awaiting confirmation, execution is partial.
    """
    try:
        result = agent_core.execute_task(task_id)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise HTTPException(500, f"Execution error: {e}")

    # Generate TTS audio
    try:
        audio_path = voice_pipeline.text_to_audio(result.text_response)
        result.audio_url = f"/audio/{audio_path.name}"
    except Exception as e:
        logger.warning(f"TTS failed (non-fatal): {e}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Text-only shortcut (no audio)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/text-input", response_model=ProcessTaskResponse, tags=["Agent"])
async def text_input(text: str = Form(...)):
    """
    Convenience endpoint: skip voice upload, process text directly.
    Returns the task plan. Call /get-response next.
    """
    task_id = str(uuid.uuid4())
    _transcripts[task_id] = text
    response = agent_core.process(text, task_id=task_id)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Human-in-the-loop confirmation
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/confirm", tags=["Agent"])
async def confirm_action(body: ConfirmActionRequest):
    """
    Approve or deny a step that required human confirmation.
    After confirming, call /get-response again to continue execution.
    """
    message = agent_core.confirm_step(body.task_id, body.step_id, body.confirmed)
    return {"task_id": body.task_id, "step_id": body.step_id,
            "confirmed": body.confirmed, "message": message}


# ─────────────────────────────────────────────────────────────────────────────
# Serve generated audio files
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audio/{filename}", tags=["Voice"])
async def serve_audio(filename: str):
    """Serve a generated TTS audio file."""
    audio_path = Path(settings.audio_output_dir) / filename
    if not audio_path.exists():
        raise HTTPException(404, "Audio file not found.")
    return FileResponse(str(audio_path), media_type="audio/mpeg")


# ─────────────────────────────────────────────────────────────────────────────
# Informational
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tools", tags=["System"])
async def list_tools():
    """List all registered tool.action pairs."""
    from tools.registry import list_tools
    return {"tools": list_tools()}


@router.get("/memory/search", tags=["Memory"])
async def search_memory(q: str, top_k: int = 3):
    """Search conversation memory for relevant context."""
    from memory.vector_store import memory
    results = memory.search(q, top_k=top_k)
    return {"query": q, "results": results}
