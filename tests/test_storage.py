from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from collectors.rss_collector import RSSItem
from database.storage import DEFAULT_DB_PATH, SQLiteStorage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


def _item(
    external_id: str = "post-1",
    title: str = "Agent MCP update",
    category: str = "ai_company",
) -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category=category,
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
        "content",
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


def test_save_article_inserts_and_updates(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    with SQLiteStorage(db_path) as storage:
        assert storage.save_article(_item()) is True
        assert storage.save_article(_item(title="Updated title")) is True

        articles = storage.list_articles()

    assert len(articles) == 1
    assert articles[0].title == "Updated title"
    assert articles[0].content == "A new Agent release."


def test_initialize_adds_content_column_to_old_schema(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.db"
    storage = SQLiteStorage(legacy_path)
    storage.connection.execute(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            external_id TEXT UNIQUE,
            source TEXT,
            category TEXT,
            title TEXT,
            link TEXT,
            summary TEXT,
            author TEXT,
            published_at TEXT,
            created_at TEXT
        )
        """
    )
    storage.connection.commit()

    storage.initialize()
    columns = [
        row["name"]
        for row in storage.connection.execute(
            "PRAGMA table_info(articles)"
        ).fetchall()
    ]

    assert "content" in columns
    storage.close()


def test_list_unanalyzed_articles_balances_categories(tmp_path: Path) -> None:
    db_path = tmp_path / "radar.db"
    with SQLiteStorage(db_path) as storage:
        storage.connection.executescript(
            ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
        )
        storage.connection.commit()
        for index in range(3):
            storage.save_article(_item(f"a{index}", category="ai_company"))
            storage.save_article(_item(f"p{index}", category="paper"))
            storage.save_article(_item(f"h{index}", category="hardware"))

        selected = storage.list_unanalyzed_articles(limit=3)
        categories = {article.category for article in selected}

    assert categories == {"ai_company", "paper", "hardware"}
