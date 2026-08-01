from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from analyzers.analyzer import AIAnalyzer
from analyzers.mock_provider import MockProvider
from analyzers.schemas import AnalysisResult
from database.analysis_repository import AnalysisRepository
from pipeline.analyzer_pipeline import AnalyzerPipeline
from reports.data_aggregator import ReportDataAggregator, ReportDataError
from reports.markdown_generator import (
    DEFAULT_PROMPT_PATH,
    MarkdownReportError,
    MarkdownReportGenerator,
)
from reports.report_pipeline import ReportPipeline, ReportPipelineError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


class FakeAggregator:
    """Aggregator stub for pipeline tests."""

    def __init__(
        self,
        results: list[AnalysisResult] | None = None,
        error: ReportDataError | None = None,
    ) -> None:
        self._results = results or []
        self._error = error

    def get_daily_analysis(
        self,
        limit: int = 10,
        min_score: int = 0,
    ) -> list[AnalysisResult]:
        if self._error is not None:
            raise self._error
        return self._results[:limit]


class FakeGenerator:
    """Generator stub for pipeline tests."""

    def __init__(
        self,
        markdown: str = "# AI Tech Radar Daily",
        generate_error: MarkdownReportError | None = None,
        save_error: MarkdownReportError | None = None,
    ) -> None:
        self._markdown = markdown
        self._generate_error = generate_error
        self._save_error = save_error

    def generate(self, results: list[AnalysisResult]) -> str:
        if self._generate_error is not None:
            raise self._generate_error
        return self._markdown

    def save_report(
        self,
        content: str,
        report_date: date | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        if self._save_error is not None:
            raise self._save_error
        directory = output_dir or Path("reports/output")
        target = report_date or date.today()
        path = directory / f"{target.isoformat()}-ai-tech-radar.md"
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


def _result() -> AnalysisResult:
    return AnalysisResult(
        importance=8,
        category="AI",
        tags=["LLM", "Agent"],
        summary="Summary.",
        impact="Impact.",
        action="Action.",
    )


def test_generate_daily_report_full_flow(tmp_path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            external_id TEXT UNIQUE,
            source TEXT,
            category TEXT,
            title TEXT,
            link TEXT,
            summary TEXT,
            content TEXT,
            author TEXT,
            published_at TEXT,
            created_at TEXT
        );
        """
    )
    connection.executescript(ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        """
        INSERT INTO articles (
            id, external_id, source, category, title, link,
            summary, content, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            1,
            "post-1",
            "Test Feed",
            "ai_company",
            "Agent framework release",
            "https://example.com/post/1",
            "OpenAI released a new agent framework.",
            "OpenAI released a new agent framework with MCP support.",
        ),
    )
    repository = AnalysisRepository(connection)
    analyzer_pipeline = AnalyzerPipeline(AIAnalyzer(MockProvider()), repository)
    analyzer_pipeline.analyze_article(1, "OpenAI released a new model")

    aggregator = ReportDataAggregator(connection)
    generator = MarkdownReportGenerator(
        AIAnalyzer(MockProvider()), prompt_config=DEFAULT_PROMPT_PATH
    )
    pipeline = ReportPipeline(aggregator, generator)

    path = pipeline.generate_daily_report(
        report_date=date(2026, 8, 1),
        output_dir=tmp_path,
    )

    assert path.name.startswith("2026-08-01-")
    assert path.name.endswith("-ai-tech-radar.md")
    assert path.read_text(encoding="utf-8") == "模拟摘要"
    connection.close()


def test_generate_daily_report_no_data_raises(tmp_path: Path) -> None:
    pipeline = ReportPipeline(FakeAggregator([]), FakeGenerator())

    with pytest.raises(ReportPipelineError, match="No analysis data"):
        pipeline.generate_daily_report(output_dir=tmp_path)


def test_generate_daily_report_query_failure_raises(tmp_path: Path) -> None:
    aggregator = FakeAggregator(error=ReportDataError("query failed"))
    pipeline = ReportPipeline(aggregator, FakeGenerator())

    with pytest.raises(ReportPipelineError, match="query failed"):
        pipeline.generate_daily_report(output_dir=tmp_path)


def test_generate_daily_report_ai_failure_raises(tmp_path: Path) -> None:
    generator = FakeGenerator(generate_error=MarkdownReportError("AI failed"))
    pipeline = ReportPipeline(FakeAggregator([_result()]), generator)

    with pytest.raises(ReportPipelineError, match="AI failed"):
        pipeline.generate_daily_report(output_dir=tmp_path)


def test_generate_daily_report_save_failure_raises(tmp_path: Path) -> None:
    generator = FakeGenerator(save_error=MarkdownReportError("save failed"))
    pipeline = ReportPipeline(FakeAggregator([_result()]), generator)

    with pytest.raises(ReportPipelineError, match="save failed"):
        pipeline.generate_daily_report(output_dir=tmp_path)
