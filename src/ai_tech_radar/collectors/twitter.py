"""X/Twitter collector using the official v2 API with a bearer token."""

from __future__ import annotations

from typing import Any, Sequence

import httpx
from loguru import logger

from ai_tech_radar.collectors.base import CollectedItem, Collector
from ai_tech_radar.collectors.common import parse_iso, truncate
from ai_tech_radar.config import TwitterSourceConfig
from ai_tech_radar.models import SourceKind


USER_AGENT = "AI-Tech-Radar/0.1 (+https://github.com/local/AI-Tech-Radar)"


class TwitterCollector(Collector):
    """Collect recent tweets from configured X accounts."""

    kind = SourceKind.TWITTER

    def __init__(
        self,
        sources: Sequence[TwitterSourceConfig],
        timeout_seconds: float = 20.0,
        per_user_limit: int = 20,
        token: str | None = None,
        api_base: str = "https://api.twitter.com/2",
    ) -> None:
        self._sources = sources
        self._timeout_seconds = timeout_seconds
        self._per_user_limit = per_user_limit
        self._token = token
        self._api_base = api_base.rstrip("/")

    def collect(self) -> list[CollectedItem]:
        """Fetch tweets for every enabled X account."""

        if not self._token:
            logger.warning(
                "X bearer token is not configured; set {} to enable Twitter collection",
                "X_BEARER_TOKEN",
            )
            return []

        enabled = [source for source in self._sources if source.enabled]
        if not enabled:
            return []

        items: list[CollectedItem] = []
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT,
        }
        with httpx.Client(timeout=self._timeout_seconds, headers=headers) as client:
            user_ids = self._lookup_users(client, enabled)
            for source in enabled:
                user_id = user_ids.get(source.username.lower())
                if user_id is None:
                    logger.warning(
                        "Could not resolve X username '{}'", source.username
                    )
                    continue
                try:
                    tweets = self._user_tweets(client, user_id)
                    items.extend(
                        self._tweet_to_item(source, tweet) for tweet in tweets
                    )
                    logger.info(
                        "Collected {} tweets from X account '{}'",
                        len(tweets),
                        source.username,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed to collect tweets for X account '{}': {}",
                        source.username,
                        exc,
                    )
        return items

    def _lookup_users(
        self, client: httpx.Client, sources: Sequence[TwitterSourceConfig]
    ) -> dict[str, str]:
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

    def _user_tweets(self, client: httpx.Client, user_id: str) -> list[dict[str, Any]]:
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

    @staticmethod
    def _tweet_to_item(
        source: TwitterSourceConfig, tweet: dict[str, Any]
    ) -> CollectedItem:
        text = str(tweet.get("text") or "")
        tweet_id = str(tweet.get("id") or "")
        return CollectedItem(
            external_id=f"tweet-{tweet_id}",
            title=truncate(text, 120),
            url=f"https://x.com/{source.username}/status/{tweet_id}",
            summary=truncate(text),
            content=text,
            author=source.username,
            published_at=parse_iso(tweet.get("created_at")),
            source_name=source.username,
            category=source.category,
            kind=SourceKind.TWITTER,
        )
