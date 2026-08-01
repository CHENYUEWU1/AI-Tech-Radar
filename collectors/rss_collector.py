"""RSS collector for AI-Tech-Radar.

Loads RSS sources from config/sources.yaml, fetches each feed with a
timeout, and normalizes entries into :class:`RSSItem` objects.
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser

from utils.config_loader import ConfigError, load_sources
from utils.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_LIMIT = 20
USER_AGENT = "AI-Tech-Radar/0.1 RSS Collector"


@dataclass(frozen=True)
class RSSSource:
    """An RSS source parsed from config/sources.yaml."""

    name: str
    category: str
    url: str
    enabled: bool = True


@dataclass(frozen=True)
class RSSItem:
    """A normalized entry collected from an RSS feed."""

    source_name: str
    category: str
    title: str
    link: str
    summary: str
    author: str | None
    published_at: datetime | None
    external_id: str


class RSSCollector:
    """Fetch and normalize entries from configured RSS sources."""

    def __init__(
        self,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self._config_dir = config_dir
        self._timeout_seconds = timeout_seconds
        self._limit = limit

    def collect(self) -> list[RSSItem]:
        """Collect items from every enabled RSS source."""

        sources = self._load_sources()
        items: list[RSSItem] = []
        for source in sources:
            if not source.enabled:
                continue
            try:
                content = self._fetch(source.url)
                items.extend(self._parse_feed(source, content))
                logger.info("Collected RSS feed '{}'", source.name)
            except Exception as exc:
                logger.error(
                    "Failed to collect RSS feed '{}': {}", source.name, exc
                )
        return items

    def _load_sources(self) -> list[RSSSource]:
        config = load_sources(self._config_dir)
        raw_sources = config.get("rss", [])
        if not isinstance(raw_sources, list):
            raise ConfigError("sources.yaml 'rss' section must be a list")
        return [self._parse_source(entry) for entry in raw_sources]

    @staticmethod
    def _parse_source(entry: Any) -> RSSSource:
        if not isinstance(entry, dict):
            raise ConfigError(f"Invalid RSS source entry: {entry!r}")
        name = str(entry.get("name", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not name:
            raise ConfigError("RSS source entry is missing 'name'")
        if not url:
            raise ConfigError(f"RSS source '{name}' is missing 'url'")
        return RSSSource(
            name=name,
            category=str(entry.get("category", "uncategorized")),
            url=url,
            enabled=bool(entry.get("enabled", True)),
        )

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout_seconds
        ) as response:
            return response.read()

    def _parse_feed(self, source: RSSSource, content: bytes) -> list[RSSItem]:
        parsed = feedparser.parse(content)
        if not parsed.entries:
            logger.warning("RSS feed '{}' returned no entries", source.name)
            return []
        return [
            self._entry_to_item(source, entry)
            for entry in parsed.entries[: self._limit]
        ]

    @staticmethod
    def _entry_to_item(source: RSSSource, entry: dict[str, Any]) -> RSSItem:
        title = str(entry.get("title") or f"Untitled from {source.name}").strip()
        link = str(entry.get("link") or entry.get("id") or source.url)
        external_id = str(
            entry.get("id")
            or entry.get("guid")
            or hashlib.md5(f"{title}|{link}".encode("utf-8")).hexdigest()
        )
        content = RSSCollector._entry_content(entry)
        summary = " ".join(str(entry.get("summary") or content or "").split())
        return RSSItem(
            source_name=source.name,
            category=source.category,
            title=title,
            link=link,
            summary=summary,
            author=entry.get("author"),
            published_at=RSSCollector._published_at(entry),
            external_id=external_id,
        )

    @staticmethod
    def _entry_content(entry: dict[str, Any]) -> str:
        raw_content = entry.get("content")
        if isinstance(raw_content, list) and raw_content:
            first = raw_content[0]
            if isinstance(first, dict):
                return str(first.get("value", ""))
            return str(first)
        return str(raw_content or "")

    @staticmethod
    def _published_at(entry: dict[str, Any]) -> datetime | None:
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if not isinstance(parsed, time.struct_time):
            return None
        return datetime.fromtimestamp(
            calendar.timegm(parsed), tz=timezone.utc
        )

    @staticmethod
    def format_item(item: RSSItem) -> str:
        """Format one collected item for terminal output."""

        lines = [
            f"Source: {item.source_name} ({item.category})",
            f"Title: {item.title}",
            f"Link: {item.link}",
        ]
        if item.published_at is not None:
            lines.append(f"Published: {item.published_at.isoformat()}")
        if item.author:
            lines.append(f"Author: {item.author}")
        if item.summary:
            lines.append(f"Summary: {item.summary}")
        return "\n".join(lines)


def main() -> int:
    """Collect RSS items from the configured sources and print them."""

    parser = argparse.ArgumentParser(
        prog="rss-collector",
        description="Collect and print RSS items for AI-Tech-Radar.",
    )
    parser.add_argument(
        "--config-dir", type=Path, default=DEFAULT_CONFIG_DIR
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT, help="Items per feed."
    )
    args = parser.parse_args()

    collector = RSSCollector(
        config_dir=args.config_dir,
        timeout_seconds=args.timeout,
        limit=args.limit,
    )
    try:
        items = collector.collect()
    except ConfigError as exc:
        logger.error("Configuration error: {}", exc)
        return 1
    except Exception as exc:
        logger.exception("RSS collection failed: {}", exc)
        return 1

    print(f"Collected {len(items)} RSS items")
    for item in items:
        print()
        print(RSSCollector.format_item(item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
