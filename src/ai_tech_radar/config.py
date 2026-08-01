"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ai_tech_radar.exceptions import ConfigError


@dataclass(frozen=True)
class RSSSourceConfig:
    """RSS source definition from config/sources.yaml."""

    name: str
    category: str
    url: str
    enabled: bool = True


@dataclass(frozen=True)
class GitHubSourceConfig:
    """GitHub source definition. A name may be an org or a full repo path."""

    name: str
    category: str
    enabled: bool = True


@dataclass(frozen=True)
class TwitterSourceConfig:
    """X/Twitter source definition."""

    username: str
    category: str
    enabled: bool = True


@dataclass(frozen=True)
class SourceConfig:
    """All configured collection sources."""

    rss: tuple[RSSSourceConfig, ...]
    github: tuple[GitHubSourceConfig, ...]
    twitter: tuple[TwitterSourceConfig, ...]


@dataclass(frozen=True)
class KeywordConfig:
    """Keyword priority groups from config/keywords.yaml."""

    high_priority: tuple[str, ...]
    medium_priority: tuple[str, ...]
    low_priority: tuple[str, ...]


@dataclass(frozen=True)
class GitHubSettings:
    """GitHub collector settings."""

    per_repo_limit: int = 10
    token_env: str = "GITHUB_TOKEN"


@dataclass(frozen=True)
class TwitterSettings:
    """X/Twitter collector settings."""

    per_user_limit: int = 20
    token_env: str = "X_BEARER_TOKEN"


@dataclass(frozen=True)
class CollectorSettings:
    """Shared collector settings."""

    request_timeout_seconds: float = 20.0
    per_source_limit: int = 20
    github: GitHubSettings = field(default_factory=GitHubSettings)
    twitter: TwitterSettings = field(default_factory=TwitterSettings)


@dataclass(frozen=True)
class AppSettings:
    """Runtime paths and collector settings."""

    database_path: Path
    report_dir: Path
    log_dir: Path
    collectors: CollectorSettings = field(default_factory=CollectorSettings)


def load_settings(config_dir: Path) -> AppSettings:
    """Load app settings, using defaults for missing sections."""

    raw = _read_yaml(config_dir / "settings.yaml")
    base_dir = config_dir.parent

    database_raw = _section(raw, "database")
    reports_raw = _section(raw, "reports")
    logs_raw = _section(raw, "logs")
    collectors_raw = _section(raw, "collectors")
    github_raw = _section(collectors_raw, "github")
    twitter_raw = _section(collectors_raw, "twitter")

    return AppSettings(
        database_path=_resolve_path(
            str(database_raw.get("path", "data/tech_radar.db")), base_dir
        ),
        report_dir=_resolve_path(
            str(reports_raw.get("dir", "reports")), base_dir
        ),
        log_dir=_resolve_path(str(logs_raw.get("dir", "logs")), base_dir),
        collectors=CollectorSettings(
            request_timeout_seconds=float(
                collectors_raw.get("request_timeout_seconds", 20.0)
            ),
            per_source_limit=int(collectors_raw.get("per_source_limit", 20)),
            github=GitHubSettings(
                per_repo_limit=int(github_raw.get("per_repo_limit", 10)),
                token_env=str(github_raw.get("token_env", "GITHUB_TOKEN")),
            ),
            twitter=TwitterSettings(
                per_user_limit=int(twitter_raw.get("per_user_limit", 20)),
                token_env=str(twitter_raw.get("token_env", "X_BEARER_TOKEN")),
            ),
        ),
    )


def load_sources(config_dir: Path) -> SourceConfig:
    """Load enabled collector sources from config/sources.yaml."""

    raw = _read_yaml(config_dir / "sources.yaml")
    return SourceConfig(
        rss=tuple(_parse_rss_sources(raw.get("rss", []))),
        github=tuple(_parse_github_sources(raw.get("github", []))),
        twitter=tuple(_parse_twitter_sources(raw.get("twitter", []))),
    )


def load_keywords(config_dir: Path) -> KeywordConfig:
    """Load keyword priority groups from config/keywords.yaml."""

    raw = _read_yaml(config_dir / "keywords.yaml")
    return KeywordConfig(
        high_priority=_parse_keywords(raw.get("high_priority", [])),
        medium_priority=_parse_keywords(raw.get("medium_priority", [])),
        low_priority=_parse_keywords(raw.get("low_priority", [])),
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a YAML mapping at top level in {path}")
    return data


def _section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"Config section '{key}' must be a mapping")
    return value


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _parse_rss_sources(entries: list[Any]) -> list[RSSSourceConfig]:
    sources: list[RSSSourceConfig] = []
    for entry in entries:
        data = _entry_mapping(entry, "rss")
        url = str(data.get("url", "")).strip()
        if not url:
            raise ConfigError(f"RSS source {data.get('name', '<unnamed>')} is missing url")
        sources.append(
            RSSSourceConfig(
                name=str(data.get("name", url)),
                category=str(data.get("category", "uncategorized")),
                url=url,
                enabled=bool(data.get("enabled", True)),
            )
        )
    return sources


def _parse_github_sources(entries: list[Any]) -> list[GitHubSourceConfig]:
    sources: list[GitHubSourceConfig] = []
    for entry in entries:
        data = _entry_mapping(entry, "github")
        name = str(data.get("name", "")).strip()
        if not name:
            raise ConfigError("GitHub source is missing name")
        sources.append(
            GitHubSourceConfig(
                name=name,
                category=str(data.get("category", "ai_company")),
                enabled=bool(data.get("enabled", True)),
            )
        )
    return sources


def _parse_twitter_sources(entries: list[Any]) -> list[TwitterSourceConfig]:
    sources: list[TwitterSourceConfig] = []
    for entry in entries:
        data = _entry_mapping(entry, "twitter")
        username = str(data.get("username", "")).strip()
        if not username:
            raise ConfigError("Twitter source is missing username")
        sources.append(
            TwitterSourceConfig(
                username=username,
                category=str(data.get("category", "community")),
                enabled=bool(data.get("enabled", True)),
            )
        )
    return sources


def _entry_mapping(entry: Any, section: str) -> dict[str, Any]:
    if isinstance(entry, str):
        key = "username" if section == "twitter" else "name"
        return {key: entry}
    if isinstance(entry, dict):
        return entry
    raise ConfigError(f"Invalid entry in config section '{section}': {entry!r}")


def _parse_keywords(entries: Any) -> tuple[str, ...]:
    if not isinstance(entries, list):
        raise ConfigError("Keyword groups must be YAML lists")
    keywords: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            raise ConfigError(f"Keyword entries must be strings, got {entry!r}")
        keyword = entry.strip()
        if keyword:
            keywords.append(keyword)
    return tuple(keywords)
