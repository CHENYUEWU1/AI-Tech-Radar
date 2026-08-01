"""Importance scoring for AI-Tech-Radar articles.

Uses an injected AI provider to evaluate information value and returns a
structured ImportanceScore.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORING_PATH = PROJECT_ROOT / "config" / "scoring.yaml"


class ImportanceScoringError(Exception):
    """Raised when importance scoring configuration or output is invalid."""


@dataclass(frozen=True)
class ImportanceScore:
    """Structured importance score produced by the AI provider."""

    title: str
    category: str
    importance_score: int
    impact: str
    reason: str
    trend: str

    def __post_init__(self) -> None:
        if not isinstance(self.importance_score, int) or not 0 <= self.importance_score <= 10:
            raise ValueError(
                "importance_score must be an integer between 0 and 10"
            )
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.category.strip():
            raise ValueError("category must not be empty")
        if not self.impact.strip():
            raise ValueError("impact must not be empty")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if not self.trend.strip():
            raise ValueError("trend must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the score with the required JSON field names."""

        return {
            "title": self.title,
            "category": self.category,
            "importance_score": self.importance_score,
            "impact": self.impact,
            "reason": self.reason,
            "trend": self.trend,
        }


class ImportanceScorer:
    """Score article information value through an AIProvider."""

    def __init__(
        self,
        provider: AIProvider,
        config_path: Path = DEFAULT_SCORING_PATH,
    ) -> None:
        self._provider = provider
        self._config = self._load_config(config_path)
        self._weights = dict(self._config.get("weights", {}))
        self._threshold = int(self._config.get("daily_min_score", 7))

    @property
    def threshold(self) -> int:
        """Return the minimum score required for the daily report."""

        return self._threshold

    def score(self, title: str, content: str) -> ImportanceScore:
        """Analyze article value and return an ImportanceScore."""

        prompt = self._build_prompt(title, content)
        result = self._provider.analyze(prompt)
        return self._to_score(title, result)

    def _build_prompt(self, title: str, content: str) -> str:
        weights_text = "\n".join(
            f"- {key}: {value}" for key, value in self._weights.items()
        )
        return (
            "请对以下 AI 科技新闻进行信息价值评分。\n\n"
            f"标题：{title}\n"
            f"内容：{content}\n\n"
            "评分范围：0-10。\n"
            "评分维度（权重）：\n"
            f"{weights_text}\n\n"
            "请只输出 JSON，不要输出 Markdown 代码块，不要输出任何解释文字。"
        )

    @staticmethod
    def _to_score(title: str, result: AnalysisResult) -> ImportanceScore:
        return ImportanceScore(
            title=title,
            category=result.category,
            importance_score=result.importance,
            impact=result.impact,
            reason=result.summary,
            trend=result.action,
        )

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ImportanceScoringError(
                f"Scoring config file not found: {path}"
            )
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ImportanceScoringError(
                f"Invalid scoring YAML in {path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ImportanceScoringError(
                f"Scoring config must be a mapping: {path}"
            )
        weights = data.get("weights")
        if not isinstance(weights, dict) or not weights:
            raise ImportanceScoringError(
                "Scoring config must define non-empty weights"
            )
        total = sum(float(value) for value in weights.values())
        if not 0.99 <= total <= 1.01:
            raise ImportanceScoringError(
                f"Scoring weights must sum to 1.0, got {total:.3f}"
            )
        return data
