"""
api/app.py – FastAPI application factory.
Applies CORS, mounts static files, registers routers, and adds middleware.
"""
from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes import router
from config import settings
from utils.logger import get_logger

logger = get_logger("api.app")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice-Enabled Agentic AI",
        description="Enterprise Workflow Automation via Voice + Multi-Agent AI",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please check logs."},
        )

    # ── Request logging middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"→ {request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"← {response.status_code} {request.url.path}")
        return response

    # ── Serve static audio files ───────────────────────────────────────────────
    audio_dir = Path(settings.audio_output_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(router, prefix="/api/v1")

    # ── Root redirect to docs ─────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "Voice Agentic AI API", "docs": "/docs", "health": "/api/v1/health"}

    logger.info("FastAPI app created")
    return app


app = create_app()
