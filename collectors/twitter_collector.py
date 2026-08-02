"""X/Twitter collector.

Loads the ``twitter`` section of config/sources.yaml and normalizes
recent tweets into :class:`RSSItem` objects so the rest of the pipeline
can process them.

Two collection modes are supported:

1. Official X v2 API when ``X_BEARER_TOKEN`` is set (requires a
   verified developer account).
2. RSSHub RSS fallback when no bearer token is configured. This needs
   no API key and works with any RSSHub instance (public, self-hosted,
   or a compatible service). Set ``RSSHUB_BASE_URL`` to override the
   default instance or provide several comma-separated fallbacks.
"""

from __future__ import annotations

import calendar
import hashlib
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import httpx

from collectors.rss_collector import RSSItem
from utils.config_loader import ConfigError, load_sources
from utils.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_PER_USER_LIMIT = 20
DEFAULT_TOKEN_ENV = "X_BEARER_TOKEN"
DEFAULT_API_BASE = "https://api.twitter.com/2"
DEFAULT_RSSHUB_ENV = "RSSHUB_BASE_URL"
DEFAULT_RSSHUB_BASES = ("https://rsshub.app",)
USER_AGENT = "AI-Tech-Radar/0.1 Twitter Collector"
_STATUS_ID_PATTERN = re.compile(r"/(?:status|statuses)/(\d+)")


@dataclass(frozen=True)
class TwitterSourceConfig:
    """An X/Twitter source parsed from config/sources.yaml."""

    username: str
    category: str = "community"
    enabled: bool = True


class TwitterCollectionError(Exception):
    """Raised when the Twitter collector cannot fetch data."""


class TwitterCollector:
    """Collect recent tweets from configured X accounts."""

    def __init__(
        self,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        per_user_limit: int = DEFAULT_PER_USER_LIMIT,
        token: str | None = None,
        token_env: str = DEFAULT_TOKEN_ENV,
        api_base: str = DEFAULT_API_BASE,
        rsshub_bases: tuple[str, ...] | None = None,
    ) -> None:
        self._config_dir = config_dir
        self._timeout_seconds = timeout_seconds
        self._per_user_limit = per_user_limit
        self._token = token if token is not None else os.environ.get(token_env)
        self._api_base = api_base.rstrip("/")
        self._rsshub_bases = rsshub_bases or self._load_rsshub_bases()
        self._failure_count = 0

    @property
    def failure_count(self) -> int:
        """Return the number of X accounts that failed to collect."""

        return self._failure_count

    @staticmethod
    def _load_rsshub_bases() -> tuple[str, ...]:
        raw = os.environ.get(DEFAULT_RSSHUB_ENV, "").strip()
        if not raw:
            return DEFAULT_RSSHUB_BASES
        return tuple(
            base.strip().rstrip("/")
            for base in raw.split(",")
            if base.strip()
        ) or DEFAULT_RSSHUB_BASES

    def collect(self) -> list[RSSItem]:
        """Collect recent tweets from every enabled X account."""

        config = load_sources(self._config_dir)
        sources = self._parse_sources(config)
        enabled = [source for source in sources if source.enabled]
        if not enabled:
            return []

        self._failure_count = 0
        if not self._token:
            return self._collect_via_rsshub(enabled)
        return self._collect_via_api(enabled)

    def _collect_via_api(
        self, sources: list[TwitterSourceConfig]
    ) -> list[RSSItem]:
        """Collect tweets through the official X v2 API."""

        items: list[RSSItem] = []
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT,
        }
        try:
            with httpx.Client(
                timeout=self._timeout_seconds, headers=headers
            ) as client:
                user_ids = self._lookup_users(client, sources)
                for source in sources:
                    user_id = user_ids.get(source.username.lower())
                    if user_id is None:
                        logger.warning(
                            "Could not resolve X username '{}'",
                            source.username,
                        )
                        continue
                    try:
                        tweets = self._user_tweets(client, user_id)
                        items.extend(
                            self._tweet_to_item(source, tweet)
                            for tweet in tweets
                        )
                        logger.info(
                            "Collected {} tweets from X account '{}'",
                            len(tweets),
                            source.username,
                        )
                    except Exception as exc:
                        self._failure_count += 1
                        logger.error(
                            "Failed to collect tweets for X account '{}': {}",
                            source.username,
                            exc,
                        )
        except Exception as exc:
            self._failure_count += len(sources)
            logger.error("Twitter collection failed: {}", exc)
        return items

    def _collect_via_rsshub(
        self, sources: list[TwitterSourceConfig]
    ) -> list[RSSItem]:
        """Collect tweets through RSSHub RSS feeds (no API key needed)."""

        logger.info(
            "X bearer token is not configured; using RSSHub RSS fallback"
        )
        items: list[RSSItem] = []
        for source in sources:
            try:
                entries = self._fetch_rsshub_entries(source.username)
                tweets = [
                    self._rsshub_entry_to_item(source, entry)
                    for entry in entries
                ]
                items.extend(tweets)
                logger.info(
                    "Collected {} tweets from X account '{}' via RSSHub",
                    len(tweets),
                    source.username,
                )
            except Exception as exc:
                self._failure_count += 1
                logger.error(
                    "Failed to collect X account '{}' via RSSHub: {}",
                    source.username,
                    exc,
                )
        return items

    @staticmethod
    def _parse_sources(config: dict[str, Any]) -> list[TwitterSourceConfig]:
        raw_sources = config.get("twitter", [])
        if not isinstance(raw_sources, list):
            raise ConfigError("sources.yaml 'twitter' section must be a list")
        return [
            TwitterCollector._parse_source(entry) for entry in raw_sources
        ]

    @staticmethod
    def _parse_source(entry: Any) -> TwitterSourceConfig:
        if isinstance(entry, str):
            return TwitterSourceConfig(username=entry.strip())
        if not isinstance(entry, dict):
            raise ConfigError(f"Invalid Twitter source entry: {entry!r}")
        username = str(entry.get("username", "")).strip()
        if not username:
            raise ConfigError("Twitter source entry is missing 'username'")
        return TwitterSourceConfig(
            username=username,
            category=str(entry.get("category", "community")),
            enabled=bool(entry.get("enabled", True)),
        )

    def _lookup_users(
        self,
        client: httpx.Client,
        sources: list[TwitterSourceConfig],
    ) -> dict[str, str]:
        """Resolve usernames to numeric user ids in one batch request."""

        usernames = [source.username for source in sources]
        response = client.get(
            f"{self._api_base}/users/by",
            params={
                "usernames": ",".join(usernames),
                "user.fields": "id,username",
            },
        )
        response.raise_for_status()
        result: dict[str, str] = {}
        for user in response.json().get("data") or []:
            username = str(user.get("username", "")).lower()
            if username:
                result[username] = str(user["id"])
        return result

    def _user_tweets(
        self, client: httpx.Client, user_id: str
    ) -> list[dict[str, Any]]:
        """Fetch the most recent tweets for a numeric user id."""

        response = client.get(
            f"{self._api_base}/users/{user_id}/tweets",
            params={
                "max_results": self._per_user_limit,
                "tweet.fields": "created_at,author_id",
                "exclude": "retweets,replies",
            },
        )
        response.raise_for_status()
        return response.json().get("data") or []

    def _fetch_rsshub_entries(self, username: str) -> list[dict[str, Any]]:
        """Fetch tweets for one account, trying each RSSHub instance."""

        last_error: Exception | None = None
        for base in self._rsshub_bases:
            url = (
                f"{base}/twitter/user/{username}"
                f"?limit={self._per_user_limit}"
            )
            try:
                content = self._fetch(url)
                parsed = feedparser.parse(content)
                if parsed.entries:
                    return parsed.entries
                last_error = TwitterCollectionError(
                    f"no entries from {base}"
                )
            except Exception as exc:
                last_error = exc
        raise TwitterCollectionError(
            f"all RSSHub instances failed for @{username}: {last_error}"
        )

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/atom+xml, "
                "application/xml, text/xml, */*",
            },
        )
        with urllib.request.urlopen(
            request, timeout=self._timeout_seconds
        ) as response:
            return response.read()

    @classmethod
    def _rsshub_entry_to_item(
        cls, source: TwitterSourceConfig, entry: dict[str, Any]
    ) -> RSSItem:
        title = str(entry.get("title") or "Untitled").strip()
        link = str(entry.get("link") or "").strip()
        summary = cls._clean_html(str(entry.get("summary") or ""))
        match = _STATUS_ID_PATTERN.search(link)
        if match:
            tweet_id = match.group(1)
        else:
            guid = str(entry.get("id") or entry.get("guid") or "")
            if guid:
                tweet_id = hashlib.md5(guid.encode("utf-8")).hexdigest()[:16]
            else:
                tweet_id = hashlib.md5(
                    f"{source.username}|{title}|{link}".encode("utf-8")
                ).hexdigest()[:16]
        return RSSItem(
            external_id=f"tweet-{tweet_id}",
            title=TwitterCollector._truncate(title, 120),
            link=link or f"https://x.com/{source.username}",
            summary=TwitterCollector._truncate(summary),
            author=source.username,
            published_at=_entry_published_at(entry),
            source_name=source.username,
            category=source.category,
        )

    @staticmethod
    def _clean_html(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()

    @staticmethod
    def _tweet_to_item(
        source: TwitterSourceConfig, tweet: dict[str, Any]
    ) -> RSSItem:
        text = str(tweet.get("text") or "")
        tweet_id = str(tweet.get("id") or "")
        return RSSItem(
            external_id=f"tweet-{tweet_id}",
            title=TwitterCollector._truncate(text, 120),
            link=f"https://x.com/{source.username}/status/{tweet_id}",
            summary=TwitterCollector._truncate(text),
            author=source.username,
            published_at=_parse_iso(tweet.get("created_at")),
            source_name=source.username,
            category=source.category,
        )

    @staticmethod
    def _truncate(text: str, limit: int = 160) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[: limit - 3]}..."


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _entry_published_at(entry: dict[str, Any]) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not isinstance(parsed, time.struct_time):
        return None
    return datetime.fromtimestamp(
        calendar.timegm(parsed), tz=timezone.utc
    )
