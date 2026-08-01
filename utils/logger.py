"""Unified logging configuration for AI-Tech-Radar."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


def setup_logger(
    log_dir: Path = DEFAULT_LOG_DIR,
    level: str = "INFO",
) -> None:
    """Configure console and file sinks with rotation."""

    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        log_dir / "app.log",
        level=level,
        rotation="1 day",
        retention="14 days",
        encoding="utf-8",
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )
