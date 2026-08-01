"""Daily report data aggregation.

Queries analysis_results for recent AI analyses without creating a
database connection or changing the database schema.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from analyzers.schemas import AnalysisResult


class ReportDataError(Exception):
    """Raised when report data aggregation fails."""


@dataclass(frozen=True)
class ReportItem:
    """An AnalysisResult joined with its original article excerpt."""

    result: AnalysisResult
    article_title: str
    article_link: str
    article_summary: str
    article_content: str
    article_published_at: str = ""

    @property
    def importance(self) -> int:
        return self.result.importance

    @property
    def category(self) -> str:
        return self.result.category

    @property
    def tags(self) -> list[str]:
        return self.result.tags

    @property
    def summary(self) -> str:
        return self.result.summary

    @property
    def impact(self) -> str:
        return self.result.impact

    @property
    def action(self) -> str:
        return self.result.action


class ReportDataAggregator:
    """Query analysis_results for daily report data."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_daily_analysis(
        self,
        limit: int = 10,
        min_score: int = 7,
    ) -> list[ReportItem]:
        """Return random analyses from the last 24 hours with original text.

        Args:
            limit: Maximum number of results to return.

        Returns:
            ReportItem objects including analysis results and article data.

        Raises:
            ReportDataError: If the query or row parsing fails.
        """

        if limit < 1:
            raise ReportDataError("limit must be at least 1")
        if min_score < 0:
            raise ReportDataError("min_score must be at least 0")

        query = """
            SELECT ar.importance, ar.category, ar.tags, ar.summary,
                   ar.impact, ar.action,
                       COALESCE(a.title, '') AS article_title,
                       COALESCE(a.link, '') AS article_link,
                       COALESCE(a.summary, '') AS article_summary,
                       COALESCE(a.content, '') AS article_content,
                       COALESCE(a.published_at, '') AS article_published_at
            FROM analysis_results ar
            LEFT JOIN articles a ON a.id = ar.article_id
        """
        params: list[Any] = []
        if min_score > 0:
            query += (
                " JOIN importance_scores s ON s.article_id = ar.article_id"
            )
        query += " WHERE ar.created_at >= datetime('now', '-1 day')"
        if min_score > 0:
            query += " AND s.importance_score >= ?"
            params.append(min_score)
        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
        try:
            rows = self._conn.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise ReportDataError(
                f"Cannot query analysis results: {exc}"
            ) from exc

        results: list[ReportItem] = []
        for row in rows:
            try:
                tags = json.loads(row[2])
                if not isinstance(tags, list):
                    raise ValueError("tags must be a JSON list")
                results.append(
                    ReportItem(
                        result=AnalysisResult(
                            importance=int(row[0]),
                            category=str(row[1]),
                            tags=tags,
                            summary=str(row[3]),
                            impact=str(row[4]),
                            action=str(row[5]),
                        ),
                        article_title=str(row[6]),
                        article_link=str(row[7]),
                        article_summary=str(row[8]),
                        article_content=str(row[9]),
                        article_published_at=str(row[10]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ReportDataError(
                    f"Cannot parse analysis result row: {exc}"
                ) from exc
        return results
