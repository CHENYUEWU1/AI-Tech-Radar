from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from analyzers.analyzer import AIAnalyzer
from analyzers.mock_provider import MockProvider
from collectors.rss_collector import RSSItem
from database.storage import SQLiteStorage
from main import ApplicationComponents, run_report_generation
from reports.data_aggregator import ReportDataAggregator
from reports.markdown_generator import (
    DEFAULT_PROMPT_PATH,
    MarkdownReportGenerator,
)
from reports.report_pipeline import ReportPipeline


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


def _insert_analysis(database: SQLiteStorage) -> None:
    database.connection.execute(
        """
        INSERT INTO analysis_results (
            article_id, importance, category, tags, summary, impact,
            action, model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            1,
            8,
            "AI",
            json.dumps(["LLM", "Agent"], ensure_ascii=False),
            "Summary.",
            "Impact.",
            "Action.",
            "mock",
        ),
    )
    database.connection.commit()


def _item() -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title="Agent MCP update",
        link="https://example.com/post/1",
        summary="A new Agent release.",
        author="Ada",
        published_at=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
        external_id="post-1",
    )


def _components(
    database: SQLiteStorage,
    report_pipeline: ReportPipeline,
) -> ApplicationComponents:
    return ApplicationComponents(
        database=database,
        collector=None,  # type: ignore[arg-type]
        analyzer=AIAnalyzer(MockProvider()),
        report_pipeline=report_pipeline,
    )


def test_run_report_generation_saves_report(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()
    database.connection.executescript(
        ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    database.save_article(_item())
    _insert_analysis(database)

    aggregator = ReportDataAggregator(database.connection)
    generator = MarkdownReportGenerator(
        AIAnalyzer(MockProvider()), prompt_config=DEFAULT_PROMPT_PATH
    )
    pipeline = ReportPipeline(aggregator, generator)
    components = _components(database, pipeline)

    path = run_report_generation(
        components, output_dir=tmp_path / "reports"
    )

    assert path is not None
    assert path.name == f"{date.today().isoformat()}-ai-tech-radar.md"
    assert path.read_text(encoding="utf-8") == "模拟摘要"
    database.close()


def test_run_report_generation_no_data_returns_none(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()
    database.connection.executescript(
        ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
    )

    aggregator = ReportDataAggregator(database.connection)
    generator = MarkdownReportGenerator(
        AIAnalyzer(MockProvider()), prompt_config=DEFAULT_PROMPT_PATH
    )
    pipeline = ReportPipeline(aggregator, generator)
    components = _components(database, pipeline)

    path = run_report_generation(
        components, output_dir=tmp_path / "reports"
    )

    assert path is None
    database.close()
