"""SQLite storage for AI-Tech-Radar.

Stores normalized RSS items in data/radar.db using only the sqlite3
standard library.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collectors.rss_collector import RSSItem
from utils.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "radar.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    external_id TEXT UNIQUE,
    source TEXT,
    category TEXT,
    title TEXT,
    link TEXT,
    summary TEXT,
    content TEXT,
    author TEXT,
    published_at TEXT,
    created_at TEXT
);
"""


class StorageError(Exception):
    """Raised when the SQLite storage layer fails."""


@dataclass(frozen=True)
class Article:
    """An article row read from the articles table."""

    id: int
    external_id: str
    source: str
    category: str
    title: str
    link: str
    summary: str
    content: str
    author: str | None
    published_at: str | None
    created_at: str


class SQLiteStorage:
    """Manage the local SQLite database used by AI-Tech-Radar."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def __enter__(self) -> SQLiteStorage:
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    @property
    def connection(self) -> sqlite3.Connection:
        """Open the database connection on first access."""

        if self._conn is None:
            try:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(self._db_path))
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error as exc:
                raise StorageError(
                    f"Cannot open database {self._db_path}: {exc}"
            ) from exc
        return self._conn

    @property
    def path(self) -> Path:
        """Return the database file path."""

        return self._db_path

    def initialize(self) -> None:
        """Create the database file and the articles table if missing."""

        if self._initialized:
            return
        try:
            self.connection.executescript(_SCHEMA)
            self._ensure_column("content", "content TEXT")
            self.connection.commit()
            self._initialized = True
        except sqlite3.Error as exc:
            raise StorageError(
                f"Cannot initialize database {self._db_path}: {exc}"
            ) from exc

    def _ensure_column(self, column: str, definition: str) -> None:
        columns = [
            row["name"]
            for row in self.connection.execute(
                "PRAGMA table_info(articles)"
            ).fetchall()
        ]
        if column not in columns:
            self.connection.execute(
                f"ALTER TABLE articles ADD COLUMN {definition}"
            )

    def save_article(self, item: RSSItem) -> bool:
        """Insert or update one RSS item. Returns True on success."""

        self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        published_at = (
            item.published_at.isoformat() if item.published_at is not None else None
        )
        try:
            cursor = self.connection.execute(
                """
                INSERT INTO articles (
                    external_id, source, category, title, link,
                    summary, content, author, published_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    source = excluded.source,
                    category = excluded.category,
                    title = excluded.title,
                    link = excluded.link,
                    summary = excluded.summary,
                    content = excluded.content,
                    author = excluded.author,
                    published_at = excluded.published_at
                """,
                (
                    item.external_id,
                    item.source_name,
                    item.category,
                    item.title,
                    item.link,
                    item.summary,
                    item.summary,
                    item.author,
                    published_at,
                    now,
                ),
            )
            self.connection.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot save article: {exc}") from exc
        return cursor.rowcount == 1

    def insert_item(self, item: RSSItem) -> bool:
        """Insert one RSS item. Returns True when the row is new."""

        self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        published_at = (
            item.published_at.isoformat() if item.published_at is not None else None
        )
        try:
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO articles (
                    external_id, source, category, title, link,
                    summary, author, published_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.external_id,
                    item.source_name,
                    item.category,
                    item.title,
                    item.link,
                    item.summary,
                    item.author,
                    published_at,
                    now,
                ),
            )
            self.connection.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot insert article: {exc}") from exc
        return cursor.rowcount == 1

    def insert_items(self, items: list[RSSItem]) -> int:
        """Insert multiple RSS items and return the number inserted."""

        inserted = 0
        for item in items:
            if self.insert_item(item):
                inserted += 1
        return inserted

    def list_articles(self, limit: int = 100) -> list[Article]:
        """Return recent articles, newest first."""

        self._ensure_initialized()
        try:
            rows = self.connection.execute(
                """
                SELECT id, external_id, source, category, title, link,
                       summary, content, author, published_at, created_at
                FROM articles
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot list articles: {exc}") from exc
        return [_row_to_article(row) for row in rows]

    def list_unanalyzed_articles(self, limit: int = 100) -> list[Article]:
        """Return articles that do not have an analysis result yet."""

        self._ensure_initialized()
        try:
            rows = self.connection.execute(
                """
                SELECT id, external_id, source, category, title, link,
                       summary, content, author, published_at, created_at
                FROM (
                    SELECT a.id, a.external_id, a.source, a.category,
                           a.title, a.link, a.summary, a.content, a.author,
                           a.published_at, a.created_at,
                           ROW_NUMBER() OVER (
                               PARTITION BY a.category ORDER BY a.id DESC
                           ) AS category_rank
                    FROM articles a
                    LEFT JOIN analysis_results ar ON ar.article_id = a.id
                    WHERE ar.id IS NULL
                )
                ORDER BY category_rank, category
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(
                f"Cannot list unanalyzed articles: {exc}"
            ) from exc
        return [_row_to_article(row) for row in rows]

    def count_articles(self) -> int:
        """Return the total number of stored articles."""

        self._ensure_initialized()
        try:
            row = self.connection.execute(
                "SELECT COUNT(*) AS total FROM articles"
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot count articles: {exc}") from exc
        return int(row["total"])

    def close(self) -> None:
        """Commit pending changes and close the connection."""

        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
            self._initialized = False

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        id=int(row["id"]),
        external_id=str(row["external_id"]),
        source=str(row["source"]),
        category=str(row["category"]),
        title=str(row["title"]),
        link=str(row["link"]),
        summary=str(row["summary"]),
        content=str(row["content"] or ""),
        author=row["author"],
        published_at=row["published_at"],
        created_at=str(row["created_at"]),
    )


def main() -> int:
    """Initialize data/radar.db and print a short summary."""

    parser = argparse.ArgumentParser(
        prog="radar-storage",
        description="Initialize the AI-Tech-Radar SQLite database.",
    )
    parser.add_argument(
        "--db-path", type=Path, default=DEFAULT_DB_PATH
    )
    args = parser.parse_args()

    try:
        with SQLiteStorage(args.db_path) as storage:
            count = storage.count_articles()
    except StorageError as exc:
        logger.error("Storage error: {}", exc)
        return 1

    print(f"Database ready: {args.db_path}")
    print(f"Articles stored: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
