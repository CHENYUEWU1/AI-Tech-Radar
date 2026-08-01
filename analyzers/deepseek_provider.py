"""DeepSeek provider skeleton.

Loads model settings from config/models.yaml and prepares the provider
for a future DeepSeek API integration. No API request is made yet.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import yaml

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "models.yaml"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0


class DeepSeekConfigError(Exception):
    """Raised when DeepSeek configuration or environment is invalid."""


class DeepSeekAPIError(Exception):
    """Raised when the DeepSeek API request fails."""


class DeepSeekProvider(AIProvider):
    """DeepSeek provider skeleton.

    The constructor only loads configuration and the API key from the
    environment. The analyze() method will be implemented in the next
    phase.
    """

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        config = self._load_config(config_path)
        ai_config = _get(config, "ai")
        model_config = _get(ai_config, "model")
        api_config = _get(ai_config, "api")
        parameters_config = _get(ai_config, "parameters")

        self._model_name = str(_get(model_config, "name"))
        self._api_key_env = str(_get(api_config, "key_env"))
        self._temperature = _load_float(parameters_config, "temperature")
        self._max_tokens = _load_int(parameters_config, "max_tokens")
        self._api_key = self._load_api_key(self._api_key_env)

    def analyze(self, article: str) -> str:
        """Send an article to DeepSeek and return the raw response text.

        This is a temporary implementation. JSON parsing and
        AnalysisResult generation arrive in the next phase.
        """

        return self._call_api(article)

    def _call_api(self, article: str) -> str:
        """Send a chat completion request and return response.text."""

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": article}],
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
