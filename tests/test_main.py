from __future__ import annotations

from pathlib import Path

import pytest

import main as main_module
from main import print_config


def _write_config(config_dir: Path) -> None:
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text(
        "rss:\n  - name: OpenAI Blog\n", encoding="utf-8"
    )
    (config_dir / "keywords.yaml").write_text(
        "high_priority:\n  - Agent\n", encoding="utf-8"
    )
    (config_dir / "models.yaml").write_text(
        """
ai:
  provider: deepseek
  model:
    name: deepseek-chat
  api:
    key_env: DEEPSEEK_API_KEY
  parameters:
    temperature: 0.2
    max_tokens: 2000
""",
        encoding="utf-8",
    )


def test_print_config_formats_sections(capsys: pytest.CaptureFixture[str]) -> None:
    sources = {"rss": [{"name": "OpenAI Blog"}]}
    keywords = {"high_priority": ["Agent"]}

    print_config(sources, keywords)

    output = capsys.readouterr().out
    assert "=== AI Tech Radar Configuration ===" in output
    assert "--- sources.yaml ---" in output
    assert "--- keywords.yaml ---" in output
    assert "OpenAI Blog" in output
    assert "high_priority" in output


def test_main_prints_loaded_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir)
    monkeypatch.setattr(main_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(main_module, "DEFAULT_DB_PATH", tmp_path / "radar.db")

    assert main_module.main() == 0

    output = capsys.readouterr().out
    assert "OpenAI Blog" in output
    assert "Agent" in output
    assert "Application initialized successfully" in output


def test_main_returns_error_on_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_module, "CONFIG_DIR", tmp_path / "missing")

    assert main_module.main() == 1
