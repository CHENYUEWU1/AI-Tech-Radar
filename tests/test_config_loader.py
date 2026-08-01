from __future__ import annotations

from pathlib import Path

import pytest

from utils.config_loader import (
    ConfigError,
    load_keywords,
    load_sources,
    load_yaml_file,
)


def test_load_yaml_file_valid(tmp_path: Path) -> None:
    path = tmp_path / "valid.yaml"
    path.write_text("name: radar\n", encoding="utf-8")

    assert load_yaml_file(path) == {"name": "radar"}


def test_load_yaml_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_yaml_file(tmp_path / "missing.yaml")


def test_load_yaml_file_invalid_raises(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("rss: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_yaml_file(path)


def test_load_yaml_file_empty_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ConfigError, match="empty"):
        load_yaml_file(path)


def test_load_yaml_file_non_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- item\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="mapping"):
        load_yaml_file(path)


def test_load_sources_and_keywords(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        "rss:\n  - name: Test Feed\n", encoding="utf-8"
    )
    (config_dir / "keywords.yaml").write_text(
        "high_priority:\n  - Agent\n", encoding="utf-8"
    )

    assert load_sources(config_dir)["rss"][0]["name"] == "Test Feed"
    assert load_keywords(config_dir)["high_priority"] == ["Agent"]
