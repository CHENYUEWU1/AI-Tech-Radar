"""AI-Tech-Radar application entry point.

Bootstraps configuration, database, collectors, analyzers, and reports.
No RSS requests, AI calls, or report generation are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from analyzers.analyzer import AIAnalyzer
from analyzers.deepseek_provider import DeepSeekConfigError, DeepSeekProvider
from analyzers.mock_provider import MockProvider
from collectors.rss_collector import RSSCollector
from database.storage import DEFAULT_DB_PATH, SQLiteStorage
from reports.data_aggregator import ReportDataAggregator
from reports.markdown_generator import (
    DEFAULT_PROMPT_PATH,
    MarkdownReportGenerator,
)
from reports.report_pipeline import ReportPipeline
from utils.config_loader import (
    ConfigError,
    load_keywords,
    load_sources,
    load_yaml_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


@dataclass
class ApplicationComponents:
    """Initialized application components."""

    database: SQLiteStorage
    collector: RSSCollector
    analyzer: AIAnalyzer
    report_pipeline: ReportPipeline


def load_all_config() -> dict[str, Any]:
    """Load all configuration files used by the application."""

    return {
        "sources": load_sources(CONFIG_DIR),
        "keywords": load_keywords(CONFIG_DIR),
        "models": load_yaml_file(CONFIG_DIR / "models.yaml"),
        "daily_report_prompt": load_yaml_file(
            PROMPTS_DIR / "daily_report.yaml"
        ),
    }


def print_config(sources: dict[str, Any], keywords: dict[str, Any]) -> None:
    """Print the loaded configuration in a readable format."""

    print("=== AI Tech Radar Configuration ===")
    print()
    print("--- sources.yaml ---")
    print(yaml.safe_dump(sources, allow_unicode=True, sort_keys=False).rstrip())
    print()
    print("--- keywords.yaml ---")
    print(yaml.safe_dump(keywords, allow_unicode=True, sort_keys=False).rstrip())


def initialize_components() -> ApplicationComponents:
    """Initialize database, collectors, analyzers, and reports."""

    logger.info("Initializing database...")
    database = SQLiteStorage(DEFAULT_DB_PATH)
    database.initialize()
    if ANALYSIS_SCHEMA_PATH.is_file():
        database.connection.executescript(
            ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        database.connection.commit()
    else:
        logger.warning("Analysis schema not found: {}", ANALYSIS_SCHEMA_PATH)

    logger.info("Initializing collectors...")
    collector = RSSCollector(config_dir=CONFIG_DIR)

    logger.info("Initializing analyzers...")
    try:
        provider = DeepSeekProvider()
        logger.info("Using DeepSeek provider")
    except DeepSeekConfigError as exc:
        logger.warning(
            "DeepSeek provider unavailable; using MockProvider: {}", exc
        )
        provider = MockProvider()
    analyzer = AIAnalyzer(provider)

    logger.info("Initializing reports...")
    aggregator = ReportDataAggregator(database.connection)
    generator = MarkdownReportGenerator(
        analyzer, prompt_config=DEFAULT_PROMPT_PATH
    )
    report_pipeline = ReportPipeline(aggregator, generator)

    return ApplicationComponents(
        database=database,
        collector=collector,
        analyzer=analyzer,
        report_pipeline=report_pipeline,
    )


def main() -> int:
    """Load configuration, initialize components, and print success."""

    try:
        config = load_all_config()
    except ConfigError as exc:
        logger.error("Failed to load configuration: {}", exc)
        return 1

    logger.info("Loaded configuration from {}", CONFIG_DIR)
    print_config(config["sources"], config["keywords"])

    try:
        initialize_components()
    except Exception as exc:
        logger.exception("Application initialization failed: {}", exc)
        return 1

    logger.info(
        "Components initialized: database, collectors, analyzers, reports"
    )
    print("Application initialized successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
