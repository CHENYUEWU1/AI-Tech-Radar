"""AI-Tech-Radar application entry point.

Bootstraps configuration, database, collectors, analyzers, and reports.
No RSS requests, AI calls, or report generation are performed here.
"""

from __future__ import annotations

import argparse
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from analyzers.analyzer import AIAnalyzer
from analyzers.deepseek_provider import DeepSeekConfigError, DeepSeekProvider
from analyzers.importance_scorer import ImportanceScorer
from analyzers.mock_provider import MockProvider
from analyzers.trend_analyzer import TrendAnalysis, TrendAnalyzer
from collectors.github_collector import GitHubCollector
from collectors.rss_collector import RSSCollector, RSSItem
from collectors.twitter_collector import TwitterCollector
from database.analysis_repository import AnalysisRepository
from database.importance_repository import ImportanceRepository
from database.storage import DEFAULT_DB_PATH, Article, SQLiteStorage
from reports.data_aggregator import ReportDataAggregator, ReportDataError
from reports.markdown_generator import (
    DEFAULT_PROMPT_PATH,
    MarkdownReportGenerator,
)
from reports.report_pipeline import ReportPipeline, ReportPipelineError
from utils.config_loader import (
    ConfigError,
    load_keywords,
    load_sources,
    load_yaml_file,
)
from utils.logger import logger, setup_logger


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"
IMPORTANCE_SCHEMA_PATH = PROJECT_ROOT / "database" / "importance_schema.sql"


@dataclass
class ApplicationComponents:
    """Initialized application components."""

    database: SQLiteStorage
    collector: RSSCollector
    analyzer: AIAnalyzer
    report_pipeline: ReportPipeline
    github_collector: GitHubCollector | None = None
    twitter_collector: TwitterCollector | None = None
    importance_scorer: ImportanceScorer | None = None
    trend_analyzer: TrendAnalyzer | None = None


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
    if IMPORTANCE_SCHEMA_PATH.is_file():
        database.connection.executescript(
            IMPORTANCE_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        database.connection.commit()
    else:
        logger.warning(
            "Importance schema not found: {}", IMPORTANCE_SCHEMA_PATH
        )

    logger.info("Initializing collectors...")
    collector = RSSCollector(config_dir=CONFIG_DIR, timeout_seconds=8)
    github_collector = GitHubCollector(config_dir=CONFIG_DIR, timeout_seconds=30)
    twitter_collector = TwitterCollector(config_dir=CONFIG_DIR)

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
    importance_scorer = ImportanceScorer(provider)
    trend_analyzer = TrendAnalyzer(provider)

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
        github_collector=github_collector,
        twitter_collector=twitter_collector,
        importance_scorer=importance_scorer,
        trend_analyzer=trend_analyzer,
    )


def run_collection(components: ApplicationComponents) -> int:
    """Collect RSS items and save new articles to SQLite.

    Args:
        components: Initialized application components.

    Returns:
        The number of newly saved articles.
    """

    logger.info("Starting RSS collection...")
    rss_items: list[RSSItem] = []
    try:
        rss_items = components.collector.collect()
    except Exception as exc:
        logger.error("RSS collection failed: {}", exc)
    logger.info("RSS collected count: {}", len(rss_items))

    github_items: list[RSSItem] = []
    if components.github_collector is not None:
        logger.info("Starting GitHub collection...")
        try:
            github_items = components.github_collector.collect()
        except Exception as exc:
            logger.error("GitHub collection failed: {}", exc)
        logger.info("GitHub fetched count: {}", len(github_items))
        logger.info(
            "GitHub failure count: {}",
            components.github_collector.failure_count,
        )

    twitter_items: list[RSSItem] = []
    if components.twitter_collector is not None:
        logger.info("Starting Twitter collection...")
        try:
            twitter_items = components.twitter_collector.collect()
        except Exception as exc:
            logger.error("Twitter collection failed: {}", exc)
        logger.info("Twitter fetched count: {}", len(twitter_items))
        logger.info(
            "Twitter failure count: {}",
            components.twitter_collector.failure_count,
        )

    items = rss_items + github_items + twitter_items
    logger.info("Collected items: {}", len(items))
    saved = 0
    failed = 0
    for item in items:
        try:
            components.database.save_article(item)
            saved += 1
        except Exception as exc:
            failed += 1
            logger.error(
                "Failed to save article '{}': {}", item.external_id, exc
            )

    logger.info("Saved items: {}", saved)
    logger.info("Failed items: {}", failed)
    return saved


def run_analysis(
    components: ApplicationComponents,
    limit: int = 20,
    per_category: int = 3,
) -> int:
    """Analyze unanalyzed articles and save AnalysisResult objects.

    Args:
        components: Initialized application components.
        limit: Maximum number of articles to analyze in this run.

    Returns:
        The number of successfully analyzed articles.
    """

    logger.info("Starting AI analysis...")
    try:
        articles = components.database.list_unanalyzed_articles(
            limit=limit,
            per_category=per_category,
        )
    except Exception as exc:
        logger.error("Failed to load unanalyzed articles: {}", exc)
        return 0

    logger.info("Pending analysis articles: {}", len(articles))
    logger.info("Starting analysis count: {}", len(articles))
    success = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_analyze_one, components, article): article
            for article in articles
        }
        for future in as_completed(futures):
            article = futures[future]
            try:
                future.result()
                success += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "Failed to analyze article {}: {}", article.id, exc
                )

    logger.info("Successfully analyzed articles: {}", success)
    logger.info("Failed analysis count: {}", failed)
    return success


def _analyze_one(
    components: ApplicationComponents,
    article: Article,
) -> None:
    content = " ".join([article.title, article.summary, article.content])
    result = components.analyzer.analyze(content)
    connection = sqlite3.connect(str(components.database.path))
    try:
        repository = AnalysisRepository(connection)
        repository.save(article.id, result, model="unknown")
    finally:
        connection.close()


def run_scoring(components: ApplicationComponents, limit: int = 20) -> int:
    """Score unprocessed articles and save importance results.

    Args:
        components: Initialized application components.
        limit: Maximum number of articles to score in this run.

    Returns:
        The number of successfully scored articles.
    """

    logger.info("Starting importance scoring...")
    if components.importance_scorer is None:
        logger.error("Importance scorer is not initialized")
        return 0

    try:
        articles = components.database.list_unscored_articles(limit=limit)
    except Exception as exc:
        logger.error("Failed to load unscored articles: {}", exc)
        return 0

    logger.info("Pending scoring articles: {}", len(articles))
    logger.info("Starting scoring count: {}", len(articles))
    success = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_score_one, components, article): article
            for article in articles
        }
        for future in as_completed(futures):
            article = futures[future]
            try:
                future.result()
                success += 1
            except Exception as exc:
                failed += 1
                logger.error(
                    "Failed to score article {}: {}", article.id, exc
                )

    logger.info("Successfully scored articles: {}", success)
    logger.info("Failed scoring count: {}", failed)
    return success


def _score_one(
    components: ApplicationComponents,
    article: Article,
) -> None:
    content = " ".join([article.summary, article.content])
    score = components.importance_scorer.score(article.title, content)
    connection = sqlite3.connect(str(components.database.path))
    try:
        repository = ImportanceRepository(connection)
        repository.save(article.id, score, model="unknown")
    finally:
        connection.close()


def run_report_generation(
    components: ApplicationComponents,
    output_dir: Path | None = None,
    trend_analysis: TrendAnalysis | None = None,
) -> Path | None:
    """Generate and save the daily report when analysis data exists.

    Args:
        components: Initialized application components.
        output_dir: Output directory override for testing.

    Returns:
        The saved report path, or None when no report was generated.
    """

    min_score = (
        components.importance_scorer.threshold
        if components.importance_scorer is not None
        else 7
    )
    try:
        aggregator = ReportDataAggregator(components.database.connection)
        results = aggregator.get_daily_analysis(min_score=min_score)
    except ReportDataError as exc:
        logger.error("Failed to load analysis results: {}", exc)
        return None

    logger.info("Analysis result count: {}", len(results))
    if not results:
        logger.warning(
            "No analysis results in the last 24 hours; skipping report"
        )
        return None

    logger.info("Starting daily report generation...")
    try:
        path = components.report_pipeline.generate_daily_report(
            output_dir=output_dir,
            min_score=min_score,
            trend_analysis=trend_analysis,
        )
    except ReportPipelineError as exc:
        logger.error("Report generation failed: {}", exc)
        return None

    logger.info("Daily report saved to {}", path)
    return path


def run_trend_analysis(
    components: ApplicationComponents,
    limit: int | None = None,
) -> TrendAnalysis | None:
    """Analyze high-value articles and produce trend intelligence.

    Args:
        components: Initialized application components.
        limit: Override for the configured analysis count.

    Returns:
        TrendAnalysis, or None when no trend data could be produced.
    """

    logger.info("Starting trend analysis...")
    if components.trend_analyzer is None:
        logger.error("Trend analyzer is not initialized")
        return None

    count = limit or components.trend_analyzer.analysis_count
    try:
        aggregator = ReportDataAggregator(components.database.connection)
        items = aggregator.get_daily_analysis(limit=count, min_score=7)
    except ReportDataError as exc:
        logger.error("Failed to load scored articles: {}", exc)
        return None

    logger.info("Trend analysis article count: {}", len(items))
    if not items:
        logger.warning("No scored articles available for trend analysis")
        return None

    try:
        trend = components.trend_analyzer.analyze(items)
        logger.info("Trend count: {}", len(trend.major_trends))
        logger.info("Trend failure count: 0")
        return trend
    except Exception as exc:
        logger.error("Trend analysis failed: {}", exc)
        logger.info("Trend failure count: 1")
        return None


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested command or the full daily pipeline by default."""

    setup_logger()

    parser = argparse.ArgumentParser(
        prog="ai-tech-radar",
        description="AI-Tech-Radar application entry point.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("collect", "analyze", "score", "report", "daily"),
        default="daily",
        help="Command to run; defaults to daily.",
    )
    args = parser.parse_args(argv if argv is not None else [])

    try:
        config = load_all_config()
    except ConfigError as exc:
        logger.error("Failed to load configuration: {}", exc)
        return 1

    logger.info("Loaded configuration from {}", CONFIG_DIR)
    print_config(config["sources"], config["keywords"])

    try:
        components = initialize_components()
    except Exception as exc:
        logger.exception("Application initialization failed: {}", exc)
        return 1

    if args.command == "collect":
        run_collection(components)
    elif args.command == "analyze":
        run_analysis(components)
    elif args.command == "score":
        run_scoring(components)
    elif args.command == "report":
        run_report_generation(components)
    else:
        run_collection(components)
        run_analysis(components)
        run_scoring(components)
        trend = run_trend_analysis(components)
        run_report_generation(components, trend_analysis=trend)

    logger.info(
        "Components initialized: database, collectors, analyzers, reports"
    )
    print("Application initialized successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
