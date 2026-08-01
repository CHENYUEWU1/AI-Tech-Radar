"""SQLite repository for AI importance scores."""

from __future__ import annotations

import sqlite3
from typing import Any

from analyzers.importance_scorer import ImportanceScore


class ImportanceRepositoryError(Exception):
    """Raised when an importance score repository operation fails."""


class ImportanceRepository:
    """Persist and load importance scores."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def save(
        self,
        article_id: int,
        score: ImportanceScore,
        model: str,
    ) -> int:
        """Insert or update an importance score and return the row id."""

        try:
            cursor = self._conn.execute(
                """
                INSERT INTO importance_scores (
                    article_id, title, category, importance_score,
                    impact, reason, trend, model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    title = excluded.title,
                    category = excluded.category,
                    importance_score = excluded.importance_score,
                    impact = excluded.impact,
                    reason = excluded.reason,
                    trend = excluded.trend,
                    model = excluded.model,
                    created_at = datetime('now')
                """,
                (
                    article_id,
                    score.title,
                    score.category,
                    score.importance_score,
                    score.impact,
                    score.reason,
                    score.trend,
                    model,
                ),
            )
            self._conn.commit()
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise ImportanceRepositoryError(
                f"Cannot save importance score: {exc}"
            ) from exc
        return int(cursor.lastrowid)

    def get_by_article_id(self, article_id: int) -> ImportanceScore | None:
        """Return the importance score for an article, if any."""

        try:
            row = self._conn.execute(
                """
                SELECT title, category, importance_score, impact,
                       reason, trend
                FROM importance_scores
                WHERE article_id = ?
                """,
                (article_id,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise ImportanceRepositoryError(
                f"Cannot load importance score: {exc}"
            ) from exc
        if row is None:
            return None
        return self._row_to_score(row)

    @staticmethod
    def _row_to_score(row: Any) -> ImportanceScore:
        try:
            return ImportanceScore(
                title=str(row[0]),
                category=str(row[1]),
                importance_score=int(row[2]),
                impact=str(row[3]),
                reason=str(row[4]),
                trend=str(row[5]),
            )
        except (TypeError, ValueError) as exc:
            raise ImportanceRepositoryError(
                f"Cannot parse importance score row: {exc}"
            ) from exc
