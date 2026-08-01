"""AI-Tech-Radar entry point.

Loads the project configuration and prints it to the terminal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from utils.config_loader import ConfigError, load_keywords, load_sources


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"


def print_config(sources: dict[str, Any], keywords: dict[str, Any]) -> None:
    """Print the loaded configuration in a readable format."""

    print("=== AI Tech Radar Configuration ===")
    print()
    print("--- sources.yaml ---")
    print(yaml.safe_dump(sources, allow_unicode=True, sort_keys=False).rstrip())
    print()
    print("--- keywords.yaml ---")
    print(yaml.safe_dump(keywords, allow_unicode=True, sort_keys=False).rstrip())


def main() -> int:
    """Load configuration and print it. Returns the process exit code."""

    try:
        sources = load_sources(CONFIG_DIR)
        keywords = load_keywords(CONFIG_DIR)
    except ConfigError as exc:
        logger.error("Failed to load configuration: {}", exc)
        return 1

    logger.info("Loaded configuration from {}", CONFIG_DIR)
    print_config(sources, keywords)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
