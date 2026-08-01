"""Collector contracts and collected item model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from ai_tech_radar.models import SourceKind


@dataclass(frozen=True)
class CollectedItem:
    """A normalized item produced by any collector."""

    external_id: str
    title: str
    url: str
    summary: str
    content: str
    author: str | None
    published_at: datetime | None
    source_name: str
    category: str
    kind: SourceKind


class Collector(ABC):
    """Base class for source collectors."""

    kind: SourceKind

    @abstractmethod
    def collect(self) -> list[CollectedItem]:
        """Fetch and normalize items from the configured sources."""
