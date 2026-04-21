"""
utils/logger.py – Application-wide logger using Loguru.
Provides structured logging with file rotation and audit trail support.
"""
import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO") -> None:
    """Configure Loguru with console + file sinks."""
    Path("./logs").mkdir(exist_ok=True)

    logger.remove()  # Remove default sink

    # Console – human-readable
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> – <level>{message}</level>",
        colorize=True,
    )

    # File – structured for audit trail
    logger.add(
        "./logs/app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} – {message}",
        serialize=False,
    )

    # Separate audit log – critical actions only
    logger.add(
        "./logs/audit.log",
        level="WARNING",
        rotation="5 MB",
        retention="90 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | AUDIT | {message}",
        filter=lambda r: "AUDIT" in r["message"],
    )


def get_logger(name: str):
    """Return a logger bound to the given module name."""
    return logger.bind(name=name)


# Initialise on import
setup_logger()
