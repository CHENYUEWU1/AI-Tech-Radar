"""DeepSeek provider.

Loads model settings from config/models.yaml, calls the DeepSeek chat
completions API, and converts the response into an AnalysisResult.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
import yaml

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "models.yaml"
DEFAULT_ANALYSIS_PROMPT_PATH = PROJECT_ROOT / "prompts" / "ai_analysis.yaml"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0


class DeepSeekConfigError(Exception):
    """Raised when DeepSeek configuration or environment is invalid."""


class DeepSeekAPIError(Exception):
    """Raised when the DeepSeek API request fails."""


class DeepSeekResponseError(Exception):
    """Raised when the DeepSeek response cannot be parsed."""


class DeepSeekProvider(AIProvider):
    """DeepSeek provider that returns structured AnalysisResult objects."""

    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG_PATH,
        prompt_path: Path = DEFAULT_ANALYSIS_PROMPT_PATH,
    ) -> None:
        config = self._load_config(config_path)
        ai_config = _get(config, "ai")
        model_config = _get(ai_config, "model")
        api_config = _get(ai_config, "api")
        parameters_config = _get(ai_config, "parameters")
        self._prompt_config = self._load_prompt_config(prompt_path)
        self._system_prompt = self._build_system_prompt()

        self._model_name = str(_get(model_config, "name"))
        self._api_key_env = str(_get(api_config, "key_env"))
        self._temperature = _load_float(parameters_config, "temperature")
        self._max_tokens = _load_int(parameters_config, "max_tokens")
        self._api_key = self._load_api_key(self._api_key_env)

    def analyze(self, article: str) -> AnalysisResult:
        """Analyze an article and return a structured AnalysisResult."""

        response_text = self._call_api(article)
        return self._parse_response(response_text)

    def _call_api(self, article: str) -> str:
        """Send a chat completion request and return response.text."""

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": self._build_user_prompt(article),
                },
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = (
                exc.response.status_code if exc.response is not None else "unknown"
            )
            raise DeepSeekAPIError(
                f"DeepSeek API returned HTTP {status_code}"
            ) from exc
        except requests.RequestException as exc:
            raise DeepSeekAPIError(
                f"DeepSeek API request failed: {exc}"
            ) from exc
        return response.text

    def _parse_response(self, response_text: str) -> AnalysisResult:
        """Parse a DeepSeek response into a validated AnalysisResult."""

        try:
            envelope = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise DeepSeekResponseError(
                "DeepSeek response is not valid JSON"
            ) from exc
        if not isinstance(envelope, dict):
            raise DeepSeekResponseError(
                "DeepSeek response must be a JSON object"
            )

        try:
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DeepSeekResponseError(
                "DeepSeek response is missing message content"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise DeepSeekResponseError(
                "DeepSeek message content must be a non-empty string"
            )

        payload = self._load_payload(content)
        return self._build_result(payload)

    @staticmethod
    def _load_payload(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            extracted = _extract_json_object(cleaned)
            try:
                payload = json.loads(extracted)
            except json.JSONDecodeError as nested_exc:
                raise DeepSeekResponseError(
                    "DeepSeek content is not valid JSON"
                ) from nested_exc
        if not isinstance(payload, dict):
            raise DeepSeekResponseError(
                "DeepSeek content must be a JSON object"
            )
        return payload

    @staticmethod
    def _build_result(payload: dict[str, Any]) -> AnalysisResult:
        required_fields = (
            "importance",
            "category",
            "tags",
            "summary",
            "impact",
            "action",
        )
        missing_fields = [
            field for field in required_fields if field not in payload
        ]
        if missing_fields:
            raise DeepSeekResponseError(
                "Missing fields in analysis result: "
                + ", ".join(missing_fields)
            )

        try:
            return AnalysisResult(
                importance=payload["importance"],
                category=payload["category"],
                tags=payload["tags"],
                summary=payload["summary"],
                impact=payload["impact"],
                action=payload["action"],
            )
        except (TypeError, ValueError) as exc:
            raise DeepSeekResponseError(
                f"Invalid analysis result fields: {exc}"
            ) from exc

    @property
    def model_name(self) -> str:
        """Return the configured model name."""

        return self._model_name

    @property
    def api_key_env(self) -> str:
        """Return the environment variable name for the API key."""

        return self._api_key_env

    @property
    def temperature(self) -> float:
        """Return the configured sampling temperature."""

        return self._temperature

    @property
    def max_tokens(self) -> int:
        """Return the configured maximum token count."""

        return self._max_tokens

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise DeepSeekConfigError(f"Config file not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise DeepSeekConfigError(f"Invalid YAML in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise DeepSeekConfigError(f"Config file must be a mapping: {path}")
        return data

    @staticmethod
    def _load_prompt_config(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise DeepSeekConfigError(f"Prompt file not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise DeepSeekConfigError(
                f"Invalid prompt YAML in {path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise DeepSeekConfigError(f"Prompt file must be a mapping: {path}")
        return data

    def _build_system_prompt(self) -> str:
        system_prompt = self._prompt_config.get("system_prompt", {})
        if isinstance(system_prompt, str):
            return system_prompt
        if not isinstance(system_prompt, dict):
            return "AI 科技分析师"
        role = str(system_prompt.get("role", "AI 科技分析师"))
        focus_areas = "\n".join(
            f"- {item}" for item in system_prompt.get("focus_areas", [])
        )
        output_format = str(system_prompt.get("output_format", ""))
        rules = "\n".join(
            f"- {item}" for item in system_prompt.get("rules", [])
        )
        return "\n".join(
            [
                f"角色：{role}",
                "关注领域：",
                focus_areas,
                "输出格式：",
                output_format,
                "规则：",
                rules,
            ]
        )

    def _build_user_prompt(self, article: str) -> str:
        template = str(self._prompt_config.get("user_prompt", ""))
        if not template:
            return article
        try:
            return template.format(title="", content=article)
        except (KeyError, IndexError, ValueError):
            return article

    @staticmethod
    def _load_api_key(env_name: str) -> str:
        api_key = os.getenv(env_name, "").strip()
        if not api_key:
            raise DeepSeekConfigError(
                f"Environment variable '{env_name}' is not set"
            )
        return api_key


def _get(container: dict[str, Any], key: str) -> Any:
    try:
        return container[key]
    except KeyError as exc:
        raise DeepSeekConfigError(
            f"Missing key '{key}' in models.yaml"
        ) from exc


def _load_float(container: dict[str, Any], key: str) -> float:
    try:
        return float(_get(container, key))
    except (TypeError, ValueError) as exc:
        raise DeepSeekConfigError(
            f"'{key}' must be a number in models.yaml"
        ) from exc


def _load_int(container: dict[str, Any], key: str) -> int:
    try:
        return int(_get(container, key))
    except (TypeError, ValueError) as exc:
        raise DeepSeekConfigError(
            f"'{key}' must be an integer in models.yaml"
        ) from exc


def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from a text response."""

    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return text
