"""GitHub collector using the public REST API."""

from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import quote

import httpx
from loguru import logger

from ai_tech_radar.collectors.base import CollectedItem, Collector
from ai_tech_radar.collectors.common import parse_iso, truncate
from ai_tech_radar.config import GitHubSourceConfig
from ai_tech_radar.models import SourceKind


USER_AGENT = "AI-Tech-Radar/0.1 (+https://github.com/local/AI-Tech-Radar)"


class GitHubCollector(Collector):
    """Collect releases for repos and public events for orgs."""

    kind = SourceKind.GITHUB

    def __init__(
        self,
        sources: Sequence[GitHubSourceConfig],
        timeout_seconds: float = 20.0,
        per_repo_limit: int = 10,
        token: str | None = None,
        api_base: str = "https://api.github.com",
    ) -> None:
        self._sources = sources
        self._timeout_seconds = timeout_seconds
        self._per_repo_limit = per_repo_limit
        self._token = token
        self._api_base = api_base.rstrip("/")

    def collect(self) -> list[CollectedItem]:
        """Fetch releases and org events from all enabled GitHub sources."""

        items: list[CollectedItem] = []
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        with httpx.Client(timeout=self._timeout_seconds, headers=headers) as client:
            for source in self._sources:
                if not source.enabled:
                    continue
                try:
                    if "/" in source.name:
                        items.extend(self._collect_repo(client, source))
                    else:
                        items.extend(self._collect_org_events(client, source))
                except Exception as exc:
                    logger.error(
                        "Failed to collect GitHub source '{}': {}", source.name, exc
                    )
        return items

    def _collect_repo(
        self, client: httpx.Client, source: GitHubSourceConfig
    ) -> list[CollectedItem]:
        endpoint = f"{self._api_base}/repos/{quote(source.name)}/releases"
        response = client.get(
            endpoint, params={"per_page": self._per_repo_limit}
        )
        response.raise_for_status()
        releases = response.json()
        items = [self._release_to_item(source, release) for release in releases]
        logger.info("Collected {} releases from GitHub repo '{}'", len(items), source.name)
        return items

    def _collect_org_events(
        self, client: httpx.Client, source: GitHubSourceConfig
    ) -> list[CollectedItem]:
        endpoint = f"{self._api_base}/orgs/{quote(source.name)}/events"
        response = client.get(endpoint, params={"per_page": 100})
        response.raise_for_status()
        items: list[CollectedItem] = []
        for event in response.json():
            item = self._event_to_item(source, event)
            if item is not None:
                items.append(item)
        logger.info(
            "Collected {} events from GitHub org '{}'", len(items), source.name
        )
        return items

    @staticmethod
    def _release_to_item(
        source: GitHubSourceConfig, release: dict[str, Any]
    ) -> CollectedItem:
        repo = source.name
        name = str(release.get("name") or release.get("tag_name") or "new release")
        body = str(release.get("body") or "")
        author_payload = release.get("author") or {}
        return CollectedItem(
            external_id=f"release-{release.get('id')}",
            title=f"[{repo}] {name}",
            url=str(release.get("html_url") or release.get("url") or ""),
            summary=truncate(body),
            content=body,
            author=author_payload.get("login") if isinstance(author_payload, dict) else None,
            published_at=parse_iso(
                release.get("published_at") or release.get("created_at")
            ),
            source_name=source.name,
            category=source.category,
            kind=SourceKind.GITHUB,
        )

    @staticmethod
    def _event_to_item(
        source: GitHubSourceConfig, event: dict[str, Any]
    ) -> CollectedItem | None:
        event_type = event.get("type")
        repo = str((event.get("repo") or {}).get("name") or source.name)
        payload = event.get("payload") or {}
        created_at = event.get("created_at")

        if event_type == "ReleaseEvent":
            release = payload.get("release") or {}
            name = str(release.get("name") or release.get("tag_name") or "new release")
            body = str(release.get("body") or "")
            return CollectedItem(
                external_id=f"event-{event.get('id')}",
                title=f"[{repo}] {name}",
                url=str(release.get("html_url") or ""),
                summary=truncate(body),
                content=body,
                author=(release.get("author") or {}).get("login")
                if isinstance(release.get("author"), dict)
                else None,
                published_at=parse_iso(created_at),
                source_name=source.name,
                category=source.category,
                kind=SourceKind.GITHUB,
            )

        if event_type == "CreateEvent" and payload.get("ref_type") == "repository":
            description = str((event.get("repo") or {}).get("description") or "")
            return CollectedItem(
                external_id=f"event-{event.get('id')}",
                title=f"[{repo}] Repository created",
                url=str((event.get("repo") or {}).get("url") or ""),
                summary=truncate(description),
                content=description,
                author=(event.get("actor") or {}).get("login")
                if isinstance(event.get("actor"), dict)
                else None,
                published_at=parse_iso(created_at),
                source_name=source.name,
                category=source.category,
                kind=SourceKind.GITHUB,
            )

        if event_type == "PushEvent":
            commits = payload.get("commits") or []
            messages = [
                str(commit.get("message", "")).splitlines()[0]
                for commit in commits[:5]
                if isinstance(commit, dict) and commit.get("message")
            ]
            summary = "\n".join(messages) or "New commits pushed."
            ref = str(payload.get("ref") or "main").removeprefix("refs/heads/")
            return CollectedItem(
                external_id=f"event-{event.get('id')}",
                title=f"[{repo}] Commits pushed to {ref}",
                url=str((event.get("repo") or {}).get("url") or ""),
                summary=truncate(summary),
                content=summary,
                author=(event.get("actor") or {}).get("login")
                if isinstance(event.get("actor"), dict)
                else None,
                published_at=parse_iso(created_at),
                source_name=source.name,
                category=source.category,
                kind=SourceKind.GITHUB,
            )

        return None
