"""
main.py – Application entry point.
Run with:  python main.py
       or: uvicorn main:app --reload
"""
import uvicorn
from api.app import app  # noqa: F401 – imported so `uvicorn main:app` works
from config import settings
from utils.logger import get_logger

logger = get_logger("main")


def main() -> None:
    logger.info(f"Starting Voice Agentic AI — env={settings.app_env}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=(settings.app_env == "development"),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
