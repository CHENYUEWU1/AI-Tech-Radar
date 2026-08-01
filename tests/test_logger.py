from __future__ import annotations

from pathlib import Path

from utils.logger import logger, setup_logger


def test_setup_logger_writes_app_and_error_logs(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    setup_logger(log_dir=log_dir)

    logger.info("logger test info")
    logger.error("logger test error")
    logger.complete()

    app_log = log_dir / "app.log"
    error_log = log_dir / "error.log"
    assert app_log.exists()
    assert error_log.exists()
    assert "logger test info" in app_log.read_text(encoding="utf-8")
    assert "logger test error" in app_log.read_text(encoding="utf-8")
    assert "logger test error" in error_log.read_text(encoding="utf-8")
    assert "logger test info" not in error_log.read_text(encoding="utf-8")
