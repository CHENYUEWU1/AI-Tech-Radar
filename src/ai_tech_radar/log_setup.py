"""Loguru setup for the application."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configure loguru with a console sink and a rotating file sink."""

    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        log_dir / "tech_radar_{time:YYYY-MM-DD}.log",
        level=level,
        rotation="1 day",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
