from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from collectors.rss_collector import RSSItem
from database.storage import DEFAULT_DB_PATH, SQLiteStorage


def _item(external_id: str = "post-1", title: str = "Agent MCP update") -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title=title,
        link=f"https://example.com/{external_id}",
        summary="A new Agent release.",
        author="Ada",
        published_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
        external_id=external_id,
    )


def test_default_db_path() -> None:
    assert DEFAULT_DB_PATH.parent.name == "data"
    assert DEFAULT_DB_PATH.name == "radar.db"


def test_initialize_creates_articles_table(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    with SQLiteStorage(db_path) as storage:
        rows = storage.connection.execute(
            "PRAGMA table_info(articles)"
        ).fetchall()

    columns = [row["name"] for row in rows]
    assert columns == [
        "id",
        "external_id",
        "source",
        "category",
        "title",
        "link",
        "summary",
        "author",
        "published_at",
        "created_at",
    ]


def test_insert_and_list_articles(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "radar.db"
    with SQLiteStorage(db_path) as storage:
        assert storage.insert_item(_item()) is True

        articles = storage.list_articles()

    assert len(articles) == 1
    article = articles[0]
    assert article.external_id == "post-1"
    assert article.source == "Test Feed"
    assert article.category == "ai_company"
    assert article.title == "Agent MCP update"
    assert article.author == "Ada"
    assert article.published_at == "2026-07-31T08:00:00+00:00"
    assert article.created_at


def test_insert_duplicate_external_id_is_ignored(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    with SQLiteStorage(db_path) as storage:
        assert storage.insert_item(_item()) is True
        assert storage.insert_item(_item()) is False
        assert storage.count_articles() == 1


def test_insert_items_returns_inserted_count(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    with SQLiteStorage(db_path) as storage:
        inserted = storage.insert_items(
            [_item("a"), _item("b"), _item("a")]
        )

    assert inserted == 2
    assert db_path.exists()
