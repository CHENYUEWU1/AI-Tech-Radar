"""Daily report data aggregation.

Queries analysis_results for recent AI analyses without creating a
database connection or changing the database schema.
"""

from __future__ import annotations

import json
import sqlite3

from analyzers.schemas import AnalysisResult


class ReportDataError(Exception):
    """Raised when report data aggregation fails."""


class ReportDataAggregator:
    """Query analysis_results for daily report data."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_daily_analysis(self, limit: int = 10) -> list[AnalysisResult]:
        """Return the most important analyses from the last 24 hours.

        Args:
            limit: Maximum number of results to return.

        Returns:
            AnalysisResult objects ordered by importance descending.

        Raises:
            ReportDataError: If the query or row parsing fails.
        """

        if limit < 1:
            raise ReportDataError("limit must be at least 1")

        try:
            rows = self._conn.execute(
                """
                SELECT importance, category, tags, summary, impact, action
                FROM analysis_results
                WHERE created_at >= datetime('now', '-1 day')
                ORDER BY importance DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise ReportDataError(
                f"Cannot query analysis results: {exc}"
            ) from exc

        results: list[AnalysisResult] = []
        for row in rows:
            try:
                tags = json.loads(row[2])
                if not isinstance(tags, list):
                    raise ValueError("tags must be a JSON list")
                results.append(
                    AnalysisResult(
                        importance=int(row[0]),
                        category=str(row[1]),
                        tags=tags,
                        summary=str(row[3]),
                        impact=str(row[4]),
                        action=str(row[5]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ReportDataError(
                    f"Cannot parse analysis result row: {exc}"
                ) from exc
        return results
