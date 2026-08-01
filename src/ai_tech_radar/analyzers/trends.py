"""Keyword trend aggregation over analyzed articles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ai_tech_radar.models import AnalyzedArticle


@dataclass(frozen=True)
class TrendItem:
    """Aggregated keyword trend."""

    keyword: str
    mentions: int
    articles: int
    total_score: int


class TrendAnalyzer:
    """Aggregate keyword counts into a ranked trend list."""

    def analyze(
        self, articles: Sequence[AnalyzedArticle], top_n: int = 10
    ) -> list[TrendItem]:
        """Return the most mentioned keywords across the given articles."""

        aggregates: dict[str, dict[str, int]] = {}
        for article in articles:
            for keyword, count in article.keywords.items():
                entry = aggregates.setdefault(
                    keyword, {"mentions": 0, "articles": 0, "score": 0}
                )
                entry["mentions"] += count
                entry["articles"] += 1
                entry["score"] += article.score

        items = [
            TrendItem(
                keyword=keyword,
                mentions=values["mentions"],
                articles=values["articles"],
                total_score=values["score"],
            )
            for keyword, values in aggregates.items()
        ]
        items.sort(
            key=lambda item: (
                -item.mentions,
                -item.articles,
                -item.total_score,
                item.keyword.lower(),
            )
        )
        return items[:top_n]
