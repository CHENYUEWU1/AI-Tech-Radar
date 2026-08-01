from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ai_tech_radar.collectors.base import CollectedItem
from ai_tech_radar.database import Database
from ai_tech_radar.models import Priority, SourceKind, SourceRecord


def _item(external_id: str, title: str) -> CollectedItem:
    return CollectedItem(
        external_id=external_id,
        title=title,
        url=f"https://example.com/{external_id}",
        summary="summary",
        content="content",
        author="author",
        published_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        source_name="Test Feed",
        category="ai_company",
        kind=SourceKind.RSS,
    )


def test_insert_and_deduplicate(tmp_path: Path) -> None:
    with Database(tmp_path / "test.db") as db:
        db.upsert_sources(
            [
                SourceRecord(
                    kind=SourceKind.RSS,
                    name="Test Feed",
                    category="ai_company",
                    url="https://example.com/rss",
                )
            ]
        )
        source_ids = db.source_id_map()

        assert db.insert_articles([_item("a", "First"), _item("b", "Second")], source_ids) == 2
        assert db.insert_articles([_item("a", "First")], source_ids) == 0
        assert len(db.list_unanalyzed_articles()) == 2


def test_save_and_list_analysis(tmp_path: Path) -> None:
    with Database(tmp_path / "test.db") as db:
        db.upsert_sources(
            [
                SourceRecord(
                    kind=SourceKind.RSS,
                    name="Test Feed",
                    category="ai_company",
                    url="https://example.com/rss",
                )
            ]
        )
        source_ids = db.source_id_map()
        db.insert_articles([_item("a", "Agent MCP news")], source_ids)
        article = db.list_unanalyzed_articles()[0]

        db.save_analysis(article.id, 6, Priority.HIGH, {"Agent": 1, "MCP": 1})
        analyzed = db.list_analyzed_articles()

        assert len(analyzed) == 1
        assert analyzed[0].score == 6
        assert analyzed[0].priority == "high"
        assert analyzed[0].keywords == {"Agent": 1, "MCP": 1}
