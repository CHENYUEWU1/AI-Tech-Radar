from __future__ import annotations

from datetime import datetime, timezone

from ai_tech_radar.analyzers.trends import TrendAnalyzer
from ai_tech_radar.models import AnalyzedArticle


def _article(keywords: dict[str, int], score: int) -> AnalyzedArticle:
    return AnalyzedArticle(
        id=score,
        title="Article",
        url="https://example.com",
        author=None,
        summary="",
        published_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        source_name="Test Feed",
        category="ai_company",
        score=score,
        priority="high",
        keywords=keywords,
    )


def test_trend_analysis_orders_by_mentions() -> None:
    articles = [
        _article({"Agent": 2, "MCP": 1}, 6),
        _article({"Agent": 1, "GPU": 3}, 5),
    ]

    trends = TrendAnalyzer().analyze(articles)

    assert [trend.keyword for trend in trends] == ["Agent", "GPU", "MCP"]
    assert trends[0].articles == 2
