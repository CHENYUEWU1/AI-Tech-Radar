from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from analyzers.analyzer import AIAnalyzer
from analyzers.mock_provider import MockProvider
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult
from database.analysis_repository import (
    AnalysisRepository,
    AnalysisRepositoryError,
)
from pipeline.analyzer_pipeline import AnalyzerPipeline, AnalyzerPipelineError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


class FakeRepository:
    """Repository stub that records save calls."""

    def __init__(self) -> None:
        self.saved: list[tuple[int, AnalysisResult, str]] = []

    def save(self, article_id: int, result: AnalysisResult, model: str) -> int:
        self.saved.append((article_id, result, model))
        return 1


class FailingProvider(AIProvider):
    """Provider that always raises during analysis."""

    def analyze(self, article: str) -> AnalysisResult:
        raise RuntimeError("provider failure")


class FailingRepository:
    """Repository stub that raises on save."""

    def save(self, article_id: int, result: AnalysisResult, model: str) -> int:
        raise AnalysisRepositoryError("save failure")


def test_analyze_article_analyzes_and_saves() -> None:
    analyzer = AIAnalyzer(MockProvider())
    repository = FakeRepository()
    pipeline = AnalyzerPipeline(analyzer, repository)

    result = pipeline.analyze_article(
        article_id=1,
        content="OpenAI released a new model",
        model="deepseek-chat",
    )

    assert isinstance(result, AnalysisResult)
    assert result.category == "AI"
    assert repository.saved == [(1, result, "deepseek-chat")]


def test_analyze_article_wraps_analysis_failure() -> None:
    pipeline = AnalyzerPipeline(
        AIAnalyzer(FailingProvider()), FakeRepository()
    )

    with pytest.raises(AnalyzerPipelineError, match="provider failure"):
        pipeline.analyze_article(1, "content")


def test_analyze_article_wraps_save_failure() -> None:
    pipeline = AnalyzerPipeline(
        AIAnalyzer(MockProvider()), FailingRepository()
    )

    with pytest.raises(AnalyzerPipelineError, match="save"):
        pipeline.analyze_article(1, "content")


def test_analyze_article_integration_with_real_repository(tmp_path: Path) -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        "CREATE TABLE articles (id INTEGER PRIMARY KEY, external_id TEXT UNIQUE);"
    )
    connection.executescript(
        ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    connection.execute(
        "INSERT INTO articles (id, external_id) VALUES (?, ?)",
        (1, "post-1"),
    )

    analyzer = AIAnalyzer(MockProvider())
    repository = AnalysisRepository(connection)
    pipeline = AnalyzerPipeline(analyzer, repository)

    result = pipeline.analyze_article(1, "OpenAI released a new model")
    stored = repository.get_by_article_id(1)

    assert result == stored
    assert result.category == "AI"
    assert result.tags == ["LLM", "Agent"]
    connection.close()
