"""SQLite storage layer."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from loguru import logger

from ai_tech_radar.collectors.base import CollectedItem
from ai_tech_radar.exceptions import StorageError
from ai_tech_radar.models import (
    AnalyzedArticle,
    ArticleRecord,
    Priority,
    SourceKind,
    SourceRecord,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_collected_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(kind, name)
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    author TEXT,
    summary TEXT,
    content TEXT,
    published_at TEXT,
    collected_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id, external_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id),
    score INTEGER NOT NULL,
    priority TEXT NOT NULL,
    keywords TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON analyses(score);
"""


class Database:
    """Thin repository over SQLite with schema initialization."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> Database:
        self.conn
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(str(self.path))
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(_SCHEMA)
                connection.commit()
            except sqlite3.Error as exc:
                raise StorageError(f"Cannot open database {self.path}: {exc}") from exc
            self._conn = connection
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def upsert_sources(self, sources: Sequence[SourceRecord]) -> None:
        """Insert or update configured sources."""

        try:
            self.conn.executemany(
                """
                INSERT INTO sources (kind, name, category, url, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(kind, name) DO UPDATE SET
                    category = excluded.category,
                    url = excluded.url,
                    enabled = excluded.enabled
                """,
                [
                    (
                        source.kind.value,
                        source.name,
                        source.category,
                        source.url,
                        int(source.enabled),
                    )
                    for source in sources
                ],
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to upsert sources: {exc}") from exc

    def source_id_map(self) -> dict[tuple[SourceKind, str], int]:
        """Return a mapping from (kind, name) to source id."""

        try:
            rows = self.conn.execute(
                "SELECT id, kind, name FROM sources"
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to load sources: {exc}") from exc
        return {(SourceKind(row["kind"]), row["name"]): int(row["id"]) for row in rows}

    def insert_articles(
        self, items: Sequence[CollectedItem], source_ids: dict[tuple[SourceKind, str], int]
    ) -> int:
        """Insert new articles, skipping duplicates. Returns inserted count."""

        inserted = 0
        now = datetime.now(timezone.utc)
        try:
            for item in items:
                source_id = source_ids.get((item.kind, item.source_name))
                if source_id is None:
                    logger.warning(
                        "No source id for {} '{}', skipping item '{}'",
                        item.kind.value,
                        item.source_name,
                        item.title,
                    )
                    continue
                cursor = self.conn.execute(
                    """
                    INSERT OR IGNORE INTO articles (
                        source_id, external_id, title, url, author,
                        summary, content, published_at, collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        item.external_id,
                        item.title,
                        item.url,
                        item.author,
                        item.summary,
                        item.content,
                        _to_iso(item.published_at),
                        _to_iso(now),
                    ),
                )
                if cursor.rowcount == 1:
                    inserted += 1
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to insert articles: {exc}") from exc
        return inserted

    def mark_sources_collected(
        self, keys: Sequence[tuple[SourceKind, str]], at: datetime
    ) -> None:
        """Record the last collection time for the given sources."""

        try:
            self.conn.executemany(
                "UPDATE sources SET last_collected_at = ? WHERE kind = ? AND name = ?",
                [(_to_iso(at), key[0].value, key[1]) for key in keys],
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to mark sources collected: {exc}") from exc

    def list_unanalyzed_articles(self, limit: int = 200) -> list[ArticleRecord]:
        """Return collected articles that do not have an analysis yet."""

        try:
            rows = self.conn.execute(
                """
                SELECT a.id, a.external_id, a.source_id, a.title, a.url, a.author,
                       a.summary, a.content, a.published_at, a.collected_at,
                       s.name AS source_name, s.kind AS source_kind, s.category
                FROM articles a
                JOIN sources s ON s.id = a.source_id
                LEFT JOIN analyses an ON an.article_id = a.id
                WHERE an.id IS NULL
                ORDER BY COALESCE(a.published_at, a.collected_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to list unanalyzed articles: {exc}") from exc
        return [_row_to_article(row) for row in rows]

    def save_analysis(
        self,
        article_id: int,
        score: int,
        priority: Priority,
        keywords: dict[str, int],
    ) -> None:
        """Persist keyword analysis for one article."""

        try:
            self.conn.execute(
                """
                INSERT INTO analyses (article_id, score, priority, keywords)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    score = excluded.score,
                    priority = excluded.priority,
                    keywords = excluded.keywords,
                    created_at = datetime('now')
                """,
                (
                    article_id,
                    score,
                    priority.value,
                    json.dumps(keywords, ensure_ascii=False),
                ),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to save analysis for article {article_id}: {exc}") from exc

    def list_analyzed_articles(
        self,
        since: datetime | None = None,
        limit: int = 100,
        min_score: int = 1,
    ) -> list[AnalyzedArticle]:
        """Return analyzed articles, highest score first."""

        query = """
            SELECT a.id, a.title, a.url, a.author, a.summary, a.published_at,
                   s.name AS source_name, s.category,
                   an.score, an.priority, an.keywords
            FROM analyses an
            JOIN articles a ON a.id = an.article_id
            JOIN sources s ON s.id = a.source_id
            WHERE an.score >= ?
        """
        params: list[Any] = [min_score]
        if since is not None:
            query += " AND COALESCE(a.published_at, a.collected_at) >= ?"
            params.append(_to_iso(since))
        query += """
            ORDER BY an.score DESC, COALESCE(a.published_at, a.collected_at) DESC
            LIMIT ?
        """
        params.append(limit)
        try:
            rows = self.conn.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to list analyzed articles: {exc}") from exc
        return [_row_to_analyzed(row) for row in rows]

    def count_articles(self, since: datetime | None = None) -> int:
        """Count collected articles, optionally since a timestamp."""

        query = "SELECT COUNT(*) AS total FROM articles"
        params: list[Any] = []
        if since is not None:
            query += " WHERE collected_at >= ?"
            params.append(_to_iso(since))
        return int(self.conn.execute(query, params).fetchone()["total"])

    def count_analyzed(self, since: datetime | None = None) -> int:
        """Count analyzed articles, optionally since a timestamp."""

        query = """
            SELECT COUNT(*) AS total
            FROM analyses an
            JOIN articles a ON a.id = an.article_id
        """
        params: list[Any] = []
        if since is not None:
            query += " WHERE COALESCE(a.published_at, a.collected_at) >= ?"
            params.append(_to_iso(since))
        return int(self.conn.execute(query, params).fetchone()["total"])

    def category_counts(self, since: datetime | None = None) -> dict[str, int]:
        """Count collected articles per source category."""

        query = """
            SELECT s.category AS category, COUNT(*) AS total
            FROM articles a
            JOIN sources s ON s.id = a.source_id
        """
        params: list[Any] = []
        if since is not None:
            query += " WHERE a.collected_at >= ?"
            params.append(_to_iso(since))
        query += " GROUP BY s.category ORDER BY total DESC"
        try:
            rows = self.conn.execute(query, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to load category counts: {exc}") from exc
        return {row["category"]: int(row["total"]) for row in rows}

    def save_report(self, report_date: str, path: Path, summary: str) -> None:
        """Upsert a generated report."""

        try:
            self.conn.execute(
                """
                INSERT INTO reports (report_date, path, summary)
                VALUES (?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    path = excluded.path,
                    summary = excluded.summary,
                    created_at = datetime('now')
                """,
                (report_date, str(path), summary),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Failed to save report {report_date}: {exc}") from exc


def _row_to_article(row: sqlite3.Row) -> ArticleRecord:
    return ArticleRecord(
        id=int(row["id"]),
        external_id=str(row["external_id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        author=row["author"],
        summary=str(row["summary"] or ""),
        content=str(row["content"] or ""),
        published_at=_parse_datetime(row["published_at"]),
        collected_at=_parse_datetime(row["collected_at"]) or datetime.now(timezone.utc),
        source_name=str(row["source_name"]),
        source_kind=SourceKind(row["source_kind"]),
        category=str(row["category"]),
    )


def _row_to_analyzed(row: sqlite3.Row) -> AnalyzedArticle:
    try:
        keywords = json.loads(row["keywords"])
    except json.JSONDecodeError:
        keywords = {}
    return AnalyzedArticle(
        id=int(row["id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        author=row["author"],
        summary=str(row["summary"] or ""),
        published_at=_parse_datetime(row["published_at"]),
        source_name=str(row["source_name"]),
        category=str(row["category"]),
        score=int(row["score"]),
        priority=str(row["priority"]),
        keywords=keywords if isinstance(keywords, dict) else {},
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat()
