from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from analyzers.schemas import AnalysisResult
from reports.data_aggregator import ReportDataAggregator, ReportDataError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def _insert(
    connection: sqlite3.Connection,
    importance: int,
    tags: list[str],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO analysis_results (
            article_id, importance, category, tags, summary, impact,
            action, model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
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


def test_get_daily_analysis_orders_by_importance() -> None:
    connection = _connection()
    _insert(connection, 5, ["LLM"], "2026-07-31 10:00:00")
    _insert(connection, 9, ["Agent", "MCP"], "2026-07-31 11:00:00")
    _insert(connection, 7, ["GPU"], "2026-07-30 10:00:00")

    aggregator = ReportDataAggregator(connection)
    results = aggregator.get_daily_analysis()

    assert [result.importance for result in results] == [9, 5]
    assert results[0].tags == ["Agent", "MCP"]
    assert isinstance(results[0], AnalysisResult)
    connection.close()


def test_get_daily_analysis_respects_limit() -> None:
    connection = _connection()
    _insert(connection, 8, ["LLM"], "2026-07-31 10:00:00")
    _insert(connection, 6, ["Agent"], "2026-07-31 11:00:00")

    results = ReportDataAggregator(connection).get_daily_analysis(limit=1)

    assert len(results) == 1
    assert results[0].importance == 8
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
        ReportDataAggregator(connection).get_daily_analysis()
    connection.close()


def test_get_daily_analysis_invalid_limit_raises() -> None:
    connection = _connection()

    with pytest.raises(ReportDataError, match="limit"):
        ReportDataAggregator(connection).get_daily_analysis(limit=0)
    connection.close()
