from __future__ import annotations

from pathlib import Path

import pytest

from ai_tech_radar.config import (
    load_keywords,
    load_settings,
    load_sources,
)
from ai_tech_radar.exceptions import ConfigError


def _write_configs(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        """
rss:
  - name: Test Feed
    category: ai_company
    url: https://example.com/rss
    enabled: true
github:
  - example/repo
twitter:
  - ExampleAI
""",
        encoding="utf-8",
    )
    (config_dir / "keywords.yaml").write_text(
        """
high_priority:
  - Agent
medium_priority:
  - RAG
low_priority:
  - VR
""",
        encoding="utf-8",
    )
    (config_dir / "settings.yaml").write_text(
        """
database:
  path: data/test.db
reports:
  dir: reports
logs:
  dir: logs
collectors:
  per_source_limit: 10
""",
        encoding="utf-8",
    )
    return config_dir


def test_load_sources(tmp_path: Path) -> None:
    sources = load_sources(_write_configs(tmp_path))

    assert len(sources.rss) == 1
    assert sources.rss[0].name == "Test Feed"
    assert sources.github[0].name == "example/repo"
    assert sources.twitter[0].username == "ExampleAI"


def test_load_keywords(tmp_path: Path) -> None:
    keywords = load_keywords(_write_configs(tmp_path))

    assert keywords.high_priority == ("Agent",)
    assert keywords.medium_priority == ("RAG",)
    assert keywords.low_priority == ("VR",)


def test_load_settings(tmp_path: Path) -> None:
    settings = load_settings(_write_configs(tmp_path))

    assert settings.database_path.name == "test.db"
    assert settings.collectors.per_source_limit == 10


def test_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text("rss: [broken\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_sources(config_dir)
