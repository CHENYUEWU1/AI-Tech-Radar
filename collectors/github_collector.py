"""GitHub AI project collector.

Uses the gh CLI to fetch GitHub repositories and filter AI-related
projects by keywords.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collectors.rss_collector import RSSItem
from utils.config_loader import ConfigError, load_sources
from utils.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_TIMEOUT_SECONDS = 60.0
AI_KEYWORDS = ("llm", "agent", "rag", "mcp", "ai")


class GitHubCollectionError(Exception):
    """Raised when the GitHub collector cannot fetch data."""


@dataclass(frozen=True)
class GitHubSourceConfig:
    """A GitHub source parsed from config/sources.yaml."""

    name: str
    category: str = "github"
    enabled: bool = True


class GitHubCollector:
    """Collect AI-related GitHub repositories through gh."""

    def __init__(
        self,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        gh_executable: str = "gh",
    ) -> None:
        self._config_dir = config_dir
        self._timeout_seconds = timeout_seconds
        self._gh_executable = gh_executable
        self._failure_count = 0

    @property
    def failure_count(self) -> int:
        """Return the number of GitHub sources that failed."""

        return self._failure_count

    def collect(self) -> list[RSSItem]:
        """Collect AI-related repositories from every enabled source."""

        config = load_sources(self._config_dir)
        sources = self._parse_sources(config)
        keywords = self._parse_keywords(config)
        self._failure_count = 0
        items: list[RSSItem] = []
        for source in sources:
            if not source.enabled:
                continue
            try:
                if "/" in source.name:
                    repo = self._gh_json(["api", f"repos/{source.name}"])
                    item = self._repo_to_item(source, repo, keywords)
                    if item is not None:
                        items.append(item)
                else:
                    repos = self._gh_json(
                        [
                            "api",
                            "--paginate",
                            f"orgs/{source.name}/repos?per_page=100&sort=updated",
                        ]
                    )
                    for repo in repos:
                        item = self._repo_to_item(source, repo, keywords)
                        if item is not None:
                            items.append(item)
                logger.info(
                    "Collected GitHub source '{}'", source.name
                )
            except Exception as exc:
                self._failure_count += 1
                logger.error(
                    "Failed to collect GitHub source '{}': {}",
                    source.name,
                    exc,
                )
        return items

    @staticmethod
    def _parse_sources(
        config: dict[str, Any],
    ) -> list[GitHubSourceConfig]:
        raw_sources = config.get("github", [])
        if not isinstance(raw_sources, list):
            raise ConfigError("sources.yaml 'github' section must be a list")
        return [
            GitHubCollector._parse_source(entry) for entry in raw_sources
        ]

    @staticmethod
    def _parse_keywords(config: dict[str, Any]) -> tuple[str, ...]:
        raw_keywords = config.get("github_keywords", [])
        if not isinstance(raw_keywords, list):
            raise ConfigError(
                "sources.yaml 'github_keywords' section must be a list"
            )
        keywords = tuple(
            str(keyword).strip().lower()
            for keyword in raw_keywords
            if str(keyword).strip()
        )
        return keywords or AI_KEYWORDS

    @staticmethod
    def _parse_source(entry: Any) -> GitHubSourceConfig:
        if isinstance(entry, str):
            return GitHubSourceConfig(name=entry)
        if not isinstance(entry, dict):
            raise ConfigError(f"Invalid GitHub source entry: {entry!r}")
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ConfigError("GitHub source entry is missing 'name'")
        return GitHubSourceConfig(
            name=name,
            category=str(entry.get("category", "github")),
            enabled=bool(entry.get("enabled", True)),
        )

    def _gh_json(self, args: list[str]) -> Any:
        try:
            completed = subprocess.run(
                [self._gh_executable, *args],
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubCollectionError(
                f"gh command failed: {exc}"
            ) from exc
        if completed.returncode != 0:
            raise GitHubCollectionError(
                f"gh command failed: {completed.stderr.strip()}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubCollectionError(
                "gh returned invalid JSON"
            ) from exc

    def _repo_to_item(
        self,
        source: GitHubSourceConfig,
        repo: dict[str, Any],
        keywords: tuple[str, ...] = AI_KEYWORDS,
    ) -> RSSItem | None:
        if not self._is_ai_repo(repo, keywords):
            return None

        full_name = str(repo.get("full_name") or repo.get("name") or source.name)
        description = str(repo.get("description") or "").strip()
        stars = int(repo.get("stargazers_count") or 0)
        forks = int(repo.get("forks_count") or 0)
        language = str(repo.get("language") or "").strip()
        updated_at = _parse_iso(repo.get("updated_at"))
        summary_parts: list[str] = []
        if description:
            summary_parts.append(description)
        summary_parts.append(f"Stars: {stars}")
        summary_parts.append(f"Forks: {forks}")
        if language:
            summary_parts.append(f"Language: {language}")
        if updated_at is not None:
            summary_parts.append(f"Updated: {updated_at.isoformat()}")

        owner = repo.get("owner") if isinstance(repo.get("owner"), dict) else {}
        return RSSItem(
            external_id=f"github-{repo.get('id')}",
            title=full_name,
            link=str(repo.get("html_url") or ""),
            summary=" | ".join(summary_parts),
            author=owner.get("login"),
            published_at=updated_at,
            source_name=source.name,
            category=source.category,
        )

    @staticmethod
    def _is_ai_repo(
        repo: dict[str, Any],
        keywords: tuple[str, ...] = AI_KEYWORDS,
    ) -> bool:
        parts = [
            repo.get("full_name"),
            repo.get("name"),
            repo.get("description"),
            " ".join(repo.get("topics") or []),
        ]
        text = " ".join(str(part) for part in parts if part).lower()
        return any(keyword in text for keyword in keywords)


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
