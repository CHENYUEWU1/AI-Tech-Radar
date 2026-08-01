"""SQLite repository for AI analysis results.

Stores ``AnalysisResult`` objects in the ``analysis_results`` table using a
caller-provided ``sqlite3.Connection``. The repository never opens a database
connection itself and never changes the database schema.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from analyzers.schemas import AnalysisResult


class AnalysisRepositoryError(Exception):
    """Raised when an analysis repository operation fails."""


class AnalysisRepository:
    """Persist and load AI analysis results from SQLite."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Initialize the repository with an existing SQLite connection."""

        self._conn = connection

    def save(self, article_id: int, result: AnalysisResult, model: str) -> int:
        """Insert an analysis result and return the new row id."""

        try:
            cursor = self._conn.execute(
                """
                INSERT INTO analysis_results (
                    article_id,
                    importance,
                    category,
                    tags,
                    summary,
                    impact,
                    action,
                    model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    result.importance,
                    result.category,
                    json.dumps(result.tags, ensure_ascii=False),
                    result.summary,
                    result.impact,
                    result.action,
                    model,
                ),
            )
            self._conn.commit()
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise AnalysisRepositoryError(
                f"Cannot save analysis result: {exc}"
            ) from exc
        return int(cursor.lastrowid)

    def get_by_article_id(self, article_id: int) -> AnalysisResult | None:
        """Return the newest analysis result for an article, if any."""

        try:
            row = self._conn.execute(
                """
                SELECT importance, category, tags, summary, impact, action
                FROM analysis_results
                WHERE article_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise AnalysisRepositoryError(
                f"Cannot load analysis result: {exc}"
            ) from exc
        if row is None:
            return None
        return self._row_to_result(row)

    @staticmethod
    def _row_to_result(row: Any) -> AnalysisResult:
        """Convert one ``analysis_results`` row into an ``AnalysisResult``."""

        try:
            return AnalysisResult(
                importance=int(row[0]),
                category=str(row[1]),
                tags=json.loads(row[2]),
                summary=str(row[3]),
                impact=str(row[4]),
                action=str(row[5]),
            )
        except (TypeError, ValueError) as exc:
            raise AnalysisRepositoryError(
                f"Cannot parse analysis result row: {exc}"
            ) from exc
