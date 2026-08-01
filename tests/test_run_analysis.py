from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from analyzers.analyzer import AIAnalyzer
from analyzers.mock_provider import MockProvider
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult
from collectors.rss_collector import RSSItem
from database.analysis_repository import AnalysisRepository
from database.storage import SQLiteStorage
from main import ApplicationComponents, run_analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_SCHEMA_PATH = PROJECT_ROOT / "database" / "analysis_schema.sql"


class FailingProvider(AIProvider):
    """Provider that simulates an API key or network failure."""

    def analyze(self, article: str) -> AnalysisResult:
        raise RuntimeError("api key failure")


def _item(external_id: str) -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title=f"Article {external_id}",
        link=f"https://example.com/{external_id}",
        summary="Agent MCP update.",
        author="Ada",
        published_at=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
        external_id=external_id,
    )


def _components(
    database: SQLiteStorage,
    analyzer: AIAnalyzer,
) -> ApplicationComponents:
    return ApplicationComponents(
        database=database,
        collector=None,  # type: ignore[arg-type]
        analyzer=analyzer,
        report_pipeline=None,  # type: ignore[arg-type]
    )


def test_run_analysis_analyzes_only_pending(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()
    database.connection.executescript(
        ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    database.connection.commit()
    for index in range(6):
        database.save_article(_item(str(index)))

    repository = AnalysisRepository(database.connection)
    articles = database.list_articles(limit=100)
    repository.save(
        articles[0].id,
        AnalysisResult(
            importance=8,
            category="AI",
            tags=["LLM"],
            summary="Summary.",
            impact="Impact.",
            action="Action.",
        ),
        model="mock",
    )

    components = _components(database, AIAnalyzer(MockProvider()))
    success = run_analysis(components, limit=5, per_category=10)

    assert success == 5
    assert database.list_unanalyzed_articles() == []
    database.close()


def test_run_analysis_api_failure_does_not_crash(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()
    database.connection.executescript(
        ANALYSIS_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    database.connection.commit()
    database.save_article(_item("a"))

    components = _components(database, AIAnalyzer(FailingProvider()))
    success = run_analysis(components)

    assert success == 0
    assert len(database.list_unanalyzed_articles()) == 1
    database.close()


def test_run_analysis_no_pending_returns_zero(tmp_path: Path) -> None:
    database = SQLiteStorage(tmp_path / "radar.db")
    database.initialize()

    components = _components(database, AIAnalyzer(MockProvider()))
    success = run_analysis(components)

    assert success == 0
    database.close()
