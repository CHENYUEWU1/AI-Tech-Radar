"""Tests for database.analysis_repository."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analyzers.schemas import AnalysisResult
from collectors.rss_collector import RSSItem
from database.analysis_repository import (
    AnalysisRepository,
    AnalysisRepositoryError,
)
from database.storage import SQLiteStorage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA = PROJECT_ROOT / "database" / "analysis_schema.sql"


def _item() -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title="Agent MCP update",
        link="https://example.com/post-1",
        summary="A new Agent release.",
        author="Ada",
        published_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
        external_id="post-1",
    )


def _result(importance: int = 8) -> AnalysisResult:
    return AnalysisResult(
        importance=importance,
        category="LLM",
        tags=["Agent", "MCP"],
        summary="A summary.",
        impact="Lower agent development cost.",
        action="Track API and ecosystem updates.",
    )


@pytest.fixture()
def repo_and_storage(
    tmp_path: Path,
) -> Iterator[tuple[AnalysisRepository, SQLiteStorage]]:
    storage = SQLiteStorage(tmp_path / "radar.db")
    storage.initialize()
    storage.connection.executescript(ANALYSIS_SCHEMA.read_text(encoding="utf-8"))
    storage.connection.commit()
    storage.insert_item(_item())
    yield AnalysisRepository(storage.connection), storage
    storage.close()


def test_save_returns_row_id_and_persists(
    repo_and_storage: tuple[AnalysisRepository, SQLiteStorage],
) -> None:
    repo, storage = repo_and_storage

    result_id = repo.save(1, _result(), "deepseek-chat")

    assert isinstance(result_id, int)
    assert result_id > 0
    row = storage.connection.execute(
        """
        SELECT article_id, importance, category, tags, summary,
               impact, action, model
        FROM analysis_results
        WHERE id = ?
        """,
        (result_id,),
    ).fetchone()
    assert row["article_id"] == 1
    assert row["importance"] == 8
    assert row["category"] == "LLM"
    assert json.loads(row["tags"]) == ["Agent", "MCP"]
    assert row["summary"] == "A summary."
    assert row["impact"] == "Lower agent development cost."
    assert row["action"] == "Track API and ecosystem updates."
    assert row["model"] == "deepseek-chat"


def test_get_by_article_id_round_trip(
    repo_and_storage: tuple[AnalysisRepository, SQLiteStorage],
) -> None:
    repo, _ = repo_and_storage
    repo.save(1, _result(), "deepseek-chat")

    loaded = repo.get_by_article_id(1)

    assert loaded == _result()


def test_get_by_article_id_returns_none_when_missing(
    repo_and_storage: tuple[AnalysisRepository, SQLiteStorage],
) -> None:
    repo, _ = repo_and_storage

    assert repo.get_by_article_id(999) is None


def test_get_by_article_id_returns_latest_result(
    repo_and_storage: tuple[AnalysisRepository, SQLiteStorage],
) -> None:
    repo, _ = repo_and_storage
    repo.save(1, _result(importance=5), "deepseek-chat")
    repo.save(1, _result(importance=9), "deepseek-chat")

    loaded = repo.get_by_article_id(1)

    assert loaded == _result(importance=9)


def test_works_with_plain_connection() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE articles (id INTEGER PRIMARY KEY);")
    conn.executescript(ANALYSIS_SCHEMA.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO articles (id) VALUES (1)")
    conn.commit()

    repo = AnalysisRepository(conn)
    result_id = repo.save(1, _result(), "deepseek-chat")

    assert isinstance(result_id, int)
    assert repo.get_by_article_id(1) == _result()
    conn.close()


def test_save_missing_table_raises_repository_error() -> None:
    conn = sqlite3.connect(":memory:")
    repo = AnalysisRepository(conn)

    with pytest.raises(AnalysisRepositoryError):
        repo.save(1, _result(), "deepseek-chat")

    conn.close()
