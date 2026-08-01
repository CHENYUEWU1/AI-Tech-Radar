"""Shared data models for the application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceKind(str, Enum):
    """Supported collector kinds."""

    RSS = "rss"
    GITHUB = "github"
    TWITTER = "twitter"


class Priority(str, Enum):
    """Keyword priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True)
class SourceRecord:
    """Persisted representation of a configured source."""

    kind: SourceKind
    name: str
    category: str
    url: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ArticleRecord:
    """Article row returned from the database."""

    id: int
    external_id: str
    title: str
    url: str
    author: str | None
    summary: str
    content: str
    published_at: datetime | None
    collected_at: datetime
    source_name: str
    source_kind: SourceKind
    category: str


@dataclass(frozen=True)
class AnalyzedArticle:
    """Article joined with its keyword analysis."""

    id: int
    title: str
    url: str
    author: str | None
    summary: str
    published_at: datetime | None
    source_name: str
    category: str
    score: int
    priority: str
    keywords: dict[str, int]
