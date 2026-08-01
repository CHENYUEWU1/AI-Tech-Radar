from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from analyzers.deepseek_provider import (
    DeepSeekAPIError,
    DeepSeekConfigError,
    DeepSeekProvider,
    DeepSeekResponseError,
)
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


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


def _provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> DeepSeekProvider:
    config_path = tmp_path / "models.yaml"
    _write_config(config_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    return DeepSeekProvider(config_path)


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


def test_analyze_returns_analysis_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    content = json.dumps(
        {
            "importance": 8,
            "category": "AI",
            "tags": ["LLM", "Agent"],
            "summary": "DeepSeek summary.",
            "impact": "Impact analysis.",
            "action": "Watch next steps.",
        },
        ensure_ascii=False,
    )

    class FakeResponse:
        text = json.dumps(
            {"choices": [{"message": {"content": content}}]},
            ensure_ascii=False,
        )

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

    result = provider.analyze("OpenAI released a new model")

    assert isinstance(result, AnalysisResult)
    assert result.importance == 8
    assert result.category == "AI"
    assert result.tags == ["LLM", "Agent"]
    assert result.summary == "DeepSeek summary."
    assert result.impact == "Impact analysis."
    assert result.action == "Watch next steps."
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "deepseek-chat"
    messages = captured["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert "只输出 JSON" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "OpenAI released a new model" in messages[1]["content"]
    assert captured["json"]["temperature"] == 0.2
    assert captured["json"]["max_tokens"] == 2000


def test_complete_returns_raw_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)

    class FakeResponse:
        text = json.dumps(
            {
                "choices": [
                    {"message": {"content": "raw trend json"}}
                ]
            },
            ensure_ascii=False,
        )

        def raise_for_status(self) -> None:
            return None

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        return FakeResponse()

    monkeypatch.setattr(
        "analyzers.deepseek_provider.requests.post", fake_post
    )

    assert provider.complete("analyze these trends") == "raw trend json"


def test_parse_response_accepts_markdown_fenced_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    payload = {
        "importance": 7,
        "category": "LLM",
        "tags": ["Agent"],
        "summary": "Summary.",
        "impact": "Impact.",
        "action": "Action.",
    }
    content = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    response_text = json.dumps(
        {"choices": [{"message": {"content": content}}]},
        ensure_ascii=False,
    )

    result = provider._parse_response(response_text)

    assert result.category == "LLM"
    assert result.importance == 7


def test_parse_response_invalid_outer_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)

    with pytest.raises(DeepSeekResponseError, match="not valid JSON"):
        provider._parse_response("not-json")


def test_parse_response_missing_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)

    with pytest.raises(DeepSeekResponseError, match="missing message content"):
        provider._parse_response('{"choices": []}')


def test_parse_response_content_not_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    response_text = json.dumps(
        {"choices": [{"message": {"content": "not-json"}}]},
        ensure_ascii=False,
    )

    with pytest.raises(DeepSeekResponseError, match="not valid JSON"):
        provider._parse_response(response_text)


def test_parse_response_missing_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    payload = {
        "importance": 6,
        "category": "AI",
        "tags": ["LLM"],
        "summary": "Summary.",
        "impact": "Impact.",
    }
    response_text = json.dumps(
        {"choices": [{"message": {"content": json.dumps(payload)}}]},
        ensure_ascii=False,
    )

    with pytest.raises(DeepSeekResponseError, match="Missing fields"):
        provider._parse_response(response_text)


def test_parse_response_invalid_importance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    payload = {
        "importance": 11,
        "category": "AI",
        "tags": ["LLM"],
        "summary": "Summary.",
        "impact": "Impact.",
        "action": "Action.",
    }
    response_text = json.dumps(
        {"choices": [{"message": {"content": json.dumps(payload)}}]},
        ensure_ascii=False,
    )

    with pytest.raises(DeepSeekResponseError, match="Invalid analysis result"):
        provider._parse_response(response_text)


def test_parse_response_extracts_json_from_extra_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path, monkeypatch)
    payload = {
        "importance": 7,
        "category": "AI",
        "tags": ["LLM"],
        "summary": "Summary.",
        "impact": "Impact.",
        "action": "Action.",
    }
    content = "Here is the result: " + json.dumps(payload, ensure_ascii=False)
    response_text = json.dumps(
        {"choices": [{"message": {"content": content}}]},
        ensure_ascii=False,
    )

    result = provider._parse_response(response_text)

    assert result.category == "AI"
    assert result.tags == ["LLM"]


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
