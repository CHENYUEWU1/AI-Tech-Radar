from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from analyzers.analyzer import AIAnalyzer
from analyzers.importance_scorer import (
    DEFAULT_SCORING_PATH,
    ImportanceScore,
    ImportanceScorer,
)
from analyzers.mock_provider import MockProvider
from collectors.rss_collector import RSSItem
from database.importance_repository import ImportanceRepository
from database.storage import SQLiteStorage
from main import ApplicationComponents, run_scoring


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMPORTANCE_SCHEMA_PATH = PROJECT_ROOT / "database" / "importance_schema.sql"


def test_importance_scorer_scores_article() -> None:
    scorer = ImportanceScorer(
        MockProvider(), config_path=DEFAULT_SCORING_PATH
    )

    score = scorer.score("Agent framework release", "A new MCP agent.")

    assert score.importance_score == 8
    assert score.category == "AI"
    assert score.to_dict()["title"] == "Agent framework release"
    assert set(score.to_dict()) == {
        "title",
        "category",
        "importance_score",
        "impact",
        "reason",
        "trend",
    }
    assert scorer.threshold == 7


def test_importance_score_validation() -> None:
    with pytest.raises(ValueError, match="0 and 10"):
        ImportanceScore(
            title="t",
            category="AI",
            importance_score=11,
            impact="i",
            reason="r",
            trend="t",
        )


def test_importance_repository_save_and_get() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(IMPORTANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    repository = ImportanceRepository(connection)
    score = ImportanceScore(
        title="Title",
        category="AI",
        importance_score=9,
        impact="Impact",
        reason="Reason",
        trend="Trend",
    )

    repository.save(1, score, model="deepseek-chat")
    stored = repository.get_by_article_id(1)

    assert stored is not None
    assert stored.importance_score == 9
    assert stored.title == "Title"
    connection.close()


def test_run_scoring_saves_scores(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()
    database.connection.executescript(
        IMPORTANCE_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    database.connection.commit()
    database.save_article(
        RSSItem(
            source_name="Test Feed",
            category="ai_company",
            title="Agent framework release",
            link="https://example.com/post/1",
            summary="A new MCP agent.",
            author="Ada",
            published_at=None,
            external_id="post-1",
        )
    )

    scorer = ImportanceScorer(MockProvider(), config_path=DEFAULT_SCORING_PATH)
    components = ApplicationComponents(
        database=database,
        collector=None,  # type: ignore[arg-type]
        analyzer=AIAnalyzer(MockProvider()),
        report_pipeline=None,  # type: ignore[arg-type]
        importance_scorer=scorer,
    )

    success = run_scoring(components, limit=10)

    assert success == 1
    connection = sqlite3.connect(str(database.path))
    repository = ImportanceRepository(connection)
    assert repository.get_by_article_id(1) is not None
    connection.close()
    database.close()
