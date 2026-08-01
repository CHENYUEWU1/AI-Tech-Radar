from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from analyzers.schemas import AnalysisResult
from reports.data_aggregator import (
    ReportDataAggregator,
    ReportDataError,
    ReportItem,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"
IMPORTANCE_SCHEMA_PATH = PROJECT_ROOT / "database" / "importance_schema.sql"


def _connection() -> sqlite3.Connection:
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
    connection.executescript(
        IMPORTANCE_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    return connection


def _insert(
    connection: sqlite3.Connection,
    importance: int,
    tags: list[str],
    created_at: str,
    article_id: int = 1,
) -> None:
    connection.execute(
        """
        INSERT INTO analysis_results (
            article_id, importance, category, tags, summary, impact,
            action, model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            importance,
            "AI",
            json.dumps(tags, ensure_ascii=False),
            "Summary",
            "Impact",
            "Action",
            "mock",
            created_at,
        ),
    )
    connection.commit()


def test_get_daily_analysis_returns_recent_results() -> None:
    connection = _connection()
    _insert(connection, 5, ["LLM"], "2026-07-31 10:00:00")
    _insert(connection, 9, ["Agent", "MCP"], "2026-07-31 11:00:00")
    _insert(connection, 7, ["GPU"], "2026-07-30 10:00:00")

    aggregator = ReportDataAggregator(connection)
    results = aggregator.get_daily_analysis(min_score=0)

    assert {result.importance for result in results} == {9, 5}
    tags_by_importance = {
        result.importance: result.tags for result in results
    }
    assert tags_by_importance[9] == ["Agent", "MCP"]
    assert isinstance(results[0], ReportItem)
    connection.close()


def test_get_daily_analysis_respects_limit() -> None:
    connection = _connection()
    _insert(connection, 8, ["LLM"], "2026-07-31 10:00:00")
    _insert(connection, 6, ["Agent"], "2026-07-31 11:00:00")

    results = ReportDataAggregator(connection).get_daily_analysis(
        limit=1, min_score=0
    )

    assert len(results) == 1
    assert results[0].importance in {8, 6}
    connection.close()


def test_get_daily_analysis_invalid_tags_raises() -> None:
    connection = _connection()
    connection.execute(
        """
        INSERT INTO analysis_results (
            article_id, importance, category, tags, summary, impact,
            action, model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 8, "AI", "not-json", "Summary", "Impact", "Action", "mock", "now"),
    )
    connection.commit()

    with pytest.raises(ReportDataError, match="Cannot parse"):
        ReportDataAggregator(connection).get_daily_analysis(min_score=0)
    connection.close()


def test_get_daily_analysis_invalid_limit_raises() -> None:
    connection = _connection()

    with pytest.raises(ReportDataError, match="limit"):
        ReportDataAggregator(connection).get_daily_analysis(limit=0)
    connection.close()


def test_get_daily_analysis_includes_original_excerpt() -> None:
    connection = _connection()
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
    connection.execute(
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
            json.dumps(["Agent"]),
            "Summary.",
            "Impact.",
            "Action.",
            "mock",
        ),
    )
    connection.commit()

    results = ReportDataAggregator(connection).get_daily_analysis(min_score=0)

    assert len(results) == 1
    assert results[0].article_title == "Agent framework release"
    assert "MCP support" in results[0].article_content
    connection.close()


def test_get_daily_analysis_filters_by_min_score() -> None:
    connection = _connection()
    _insert(connection, 9, ["Agent"], "2026-08-01 10:00:00", article_id=1)
    _insert(connection, 5, ["LLM"], "2026-08-01 11:00:00", article_id=2)
    connection.execute(
        """
        INSERT INTO importance_scores (
            article_id, title, category, importance_score,
            impact, reason, trend, model
        ) VALUES (1, 'High', 'AI', 9, 'i', 'r', 't', 'mock'),
                 (2, 'Low', 'AI', 5, 'i', 'r', 't', 'mock')
        """
    )
    connection.commit()

    results = ReportDataAggregator(connection).get_daily_analysis(min_score=7)

    assert len(results) == 1
    assert results[0].importance == 9
    connection.close()
