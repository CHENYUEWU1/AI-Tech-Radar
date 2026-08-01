from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from analyzers.deepseek_provider import (
    DeepSeekAPIError,
    DeepSeekConfigError,
    DeepSeekProvider,
)
from analyzers.provider import AIProvider


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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


def test_deepseek_provider_loads_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    provider = DeepSeekProvider(config_path)

    assert isinstance(provider, AIProvider)
    assert provider.model_name == "deepseek-chat"
    assert provider.api_key_env == "DEEPSEEK_API_KEY"
    assert provider.temperature == 0.2
    assert provider.max_tokens == 2000


def test_missing_api_key_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(DeepSeekConfigError, match="not set"):
        DeepSeekProvider(config_path)


def test_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(DeepSeekConfigError, match="not found"):
        DeepSeekProvider(tmp_path / "missing.yaml")


def test_analyze_returns_response_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeResponse:
        text = '{"choices": [{"message": {"content": "ok"}}]}'

        def raise_for_status(self) -> None:
            return None

    captured: dict[str, Any] = {}

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(
        "analyzers.deepseek_provider.requests.post", fake_post
    )

    provider = DeepSeekProvider(config_path)
    result = provider.analyze("OpenAI released a new model")

    assert result == FakeResponse.text
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "deepseek-chat"
    assert captured["json"]["messages"] == [
        {"role": "user", "content": "OpenAI released a new model"}
    ]


def test_analyze_raises_on_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class FakeHTTPError(requests.HTTPError):
        def __init__(self) -> None:
            super().__init__("HTTP error")
            self.response = type(
                "Response",
                (),
                {"status_code": 401},
            )()

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> None:
        raise FakeHTTPError()

    monkeypatch.setattr(
        "analyzers.deepseek_provider.requests.post", fake_post
    )

    provider = DeepSeekProvider(config_path)

    with pytest.raises(DeepSeekAPIError, match="HTTP 401"):
        provider.analyze("OpenAI released a new model")


def test_analyze_raises_on_network_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> None:
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(
        "analyzers.deepseek_provider.requests.post", fake_post
    )

    provider = DeepSeekProvider(config_path)

    with pytest.raises(DeepSeekAPIError, match="request failed"):
        provider.analyze("OpenAI released a new model")
