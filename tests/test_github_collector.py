from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from collectors.github_collector import (
    GitHubCollectionError,
    GitHubCollector,
)
from utils.config_loader import ConfigError


def _write_config(config_dir: Path, github_yaml: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "sources.yaml").write_text(github_yaml, encoding="utf-8")


def _ai_repo() -> dict[str, Any]:
    return {
        "id": 1,
        "full_name": "test-org/awesome-agent",
        "name": "awesome-agent",
        "description": "An LLM agent framework with RAG and MCP support.",
        "html_url": "https://github.com/test-org/awesome-agent",
        "stargazers_count": 123,
        "forks_count": 45,
        "language": "Python",
        "updated_at": "2026-08-01T08:00:00Z",
        "topics": ["llm", "agent"],
        "owner": {"login": "test-org"},
    }


def _non_ai_repo() -> dict[str, Any]:
    return {
        "id": 2,
        "full_name": "test-org/weather-api",
        "name": "weather-api",
        "description": "Weather forecast API.",
        "html_url": "https://github.com/test-org/weather-api",
        "stargazers_count": 10,
        "forks_count": 2,
        "language": "Go",
        "updated_at": "2026-08-01T08:00:00Z",
        "topics": [],
        "owner": {"login": "test-org"},
    }


def test_repo_to_item_contains_stars_and_url() -> None:
    source = GitHubCollector._parse_source(
        {"name": "test-org", "category": "agent", "enabled": True}
    )

    item = GitHubCollector._repo_to_item(
        GitHubCollector(config_dir=Path("config")), source, _ai_repo()
    )

    assert item is not None
    assert item.title == "test-org/awesome-agent"
    assert item.link == "https://github.com/test-org/awesome-agent"
    assert "Stars: 123" in item.summary
    assert "Forks: 45" in item.summary
    assert "Language: Python" in item.summary
    assert "LLM agent" in item.summary


def test_non_ai_repo_is_filtered() -> None:
    source = GitHubCollector._parse_source("test-org")

    item = GitHubCollector._repo_to_item(
        GitHubCollector(config_dir=Path("config")), source, _non_ai_repo()
    )

    assert item is None


def test_collect_org_filters_ai_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
github:
  - name: test-org
    category: agent
    enabled: true
""",
    )
    collector = GitHubCollector(config_dir=config_dir)
    monkeypatch.setattr(
        collector,
        "_gh_json",
        lambda args: [_ai_repo(), _non_ai_repo()],
    )

    items = collector.collect()

    assert len(items) == 1
    assert items[0].title == "test-org/awesome-agent"


def test_collect_handles_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
github:
  - name: broken-org
    category: agent
    enabled: true
""",
    )
    collector = GitHubCollector(config_dir=config_dir)

    def fake_gh_json(args: list[str]) -> Any:
        raise GitHubCollectionError("gh not authenticated")

    monkeypatch.setattr(collector, "_gh_json", fake_gh_json)

    assert collector.collect() == []
    assert collector.failure_count == 1


def test_keywords_loaded_from_config() -> None:
    keywords = GitHubCollector._parse_keywords(
        {"github_keywords": ["LLM", "Agent", "RAG"]}
    )

    assert keywords == ("llm", "agent", "rag")


def test_invalid_github_section_raises(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir, "github: not-a-list\n")

    with pytest.raises(ConfigError, match="must be a list"):
        GitHubCollector(config_dir=config_dir).collect()
