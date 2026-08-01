from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ai_tech_radar.analyzers.trends import TrendItem
from ai_tech_radar.models import AnalyzedArticle
from ai_tech_radar.reporters.daily import DailyReporter


def test_daily_report_render_and_write(tmp_path: Path) -> None:
    article = AnalyzedArticle(
        id=1,
        title="Agent MCP release",
        url="https://example.com/post",
        author="Ada",
        summary="A new release.",
        published_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
        source_name="Test Feed",
        category="ai_company",
        score=6,
        priority="high",
        keywords={"Agent": 1},
    )
    trend = TrendItem(keyword="Agent", mentions=1, articles=1, total_score=6)
    stats = {
        "articles": 1,
        "analyzed": 1,
        "sources": 1,
        "categories": {"ai_company": 1},
    }

    reporter = DailyReporter()
    content = reporter.render("2026-07-31", [article], [trend], stats)
    path = reporter.write("2026-07-31", content, tmp_path)

    assert "# AI Tech Radar - 2026-07-31" in content
    assert "Agent MCP release" in content
    assert path.exists()
