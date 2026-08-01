"""RSS/Atom collector built on feedparser and httpx."""

from __future__ import annotations

import calendar
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Sequence

import feedparser
import httpx
from loguru import logger

from ai_tech_radar.collectors.base import CollectedItem, Collector
from ai_tech_radar.collectors.common import truncate
from ai_tech_radar.config import RSSSourceConfig
from ai_tech_radar.models import SourceKind


USER_AGENT = "AI-Tech-Radar/0.1 (+https://github.com/local/AI-Tech-Radar)"


class RSSCollector(Collector):
    """Collect entries from configured RSS and Atom feeds."""

    kind = SourceKind.RSS

    def __init__(
        self,
        sources: Sequence[RSSSourceConfig],
        timeout_seconds: float = 20.0,
        limit: int = 20,
    ) -> None:
        self._sources = sources
        self._timeout_seconds = timeout_seconds
        self._limit = limit

    def collect(self) -> list[CollectedItem]:
        """Fetch every enabled feed and normalize its latest entries."""

        items: list[CollectedItem] = []
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=self._timeout_seconds, headers=headers) as client:
            for source in self._sources:
                if not source.enabled:
                    continue
                try:
                    response = client.get(source.url, follow_redirects=True)
                    response.raise_for_status()
                    parsed = feedparser.parse(response.content)
                    if not parsed.entries:
                        logger.warning(
                            "RSS source '{}' returned no entries", source.name
                        )
                        continue
                    for entry in parsed.entries[: self._limit]:
                        items.append(self._entry_to_item(source, entry))
                    logger.info(
                        "Collected {} entries from RSS source '{}'",
                        min(len(parsed.entries), self._limit),
                        source.name,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to collect RSS source '{}': {}", source.name, exc
                    )
        return items

    @staticmethod
    def _entry_to_item(source: RSSSourceConfig, entry: dict[str, Any]) -> CollectedItem:
        title = str(entry.get("title") or f"Untitled from {source.name}").strip()
        link = str(entry.get("link") or entry.get("id") or source.url)
        external_id = str(
            entry.get("id")
            or entry.get("guid")
            or link
            or hashlib.md5(f"{title}|{link}".encode("utf-8")).hexdigest()
        )
        content = RSSCollector._entry_content(entry)
        return CollectedItem(
            external_id=external_id,
            title=title,
            url=link,
            summary=truncate(str(entry.get("summary") or content or "")),
            content=content,
            author=entry.get("author"),
            published_at=RSSCollector._published_at(entry),
            source_name=source.name,
            category=source.category,
            kind=SourceKind.RSS,
        )

    @staticmethod
    def _entry_content(entry: dict[str, Any]) -> str:
        raw = entry.get("content")
        if isinstance(raw, list) and raw:
            first = raw[0]
            return str(first.get("value", "")) if isinstance(first, dict) else str(first)
        return str(raw or "")

    @staticmethod
    def _published_at(entry: dict[str, Any]) -> datetime | None:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not isinstance(parsed, time.struct_time):
            return None
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
