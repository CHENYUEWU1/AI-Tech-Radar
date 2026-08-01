"""Configuration loader for AI-Tech-Radar.

Loads config/sources.yaml and config/keywords.yaml using PyYAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when a configuration file cannot be loaded."""


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from *path*.

    Raises ConfigError if the file is missing, empty, malformed, or does
    not contain a mapping at the top level.
    """

    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration file {path}: {exc}") from exc

    if data is None:
        raise ConfigError(f"Configuration file is empty: {path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file must contain a mapping: {path}")
    return data


def load_sources(config_dir: Path) -> dict[str, Any]:
    """Load source definitions from config/sources.yaml."""

    return load_yaml_file(config_dir / "sources.yaml")


def load_keywords(config_dir: Path) -> dict[str, Any]:
    """Load keyword priorities from config/keywords.yaml."""

    return load_yaml_file(config_dir / "keywords.yaml")
