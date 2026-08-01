"""Trend intelligence analyzer.

Uses an AI provider to turn high-value articles into trend intelligence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult
from reports.data_aggregator import ReportItem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TREND_CONFIG = PROJECT_ROOT / "config" / "trend.yaml"


class TrendAnalysisError(Exception):
    """Raised when trend analysis fails."""


@dataclass(frozen=True)
class TrendAnalysis:
    """Structured trend intelligence output."""

    major_trends: list[str]
    domestic_analysis: str
    global_analysis: str
    information_gap: str
    future_prediction: str
    opportunities: list[str]

    def __post_init__(self) -> None:
        if not isinstance(self.major_trends, list) or not all(
            isinstance(item, str) and item.strip() for item in self.major_trends
        ):
            raise ValueError("major_trends must be a list of non-empty strings")
        if not isinstance(self.opportunities, list) or not all(
            isinstance(item, str) and item.strip()
            for item in self.opportunities
        ):
            raise ValueError(
                "opportunities must be a list of non-empty strings"
            )
        for field in (
            self.domestic_analysis,
            self.global_analysis,
            self.information_gap,
            self.future_prediction,
        ):
            if not isinstance(field, str) or not field.strip():
                raise ValueError("trend text fields must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize trend analysis for report prompts."""

        return {
            "major_trends": self.major_trends,
            "domestic_analysis": self.domestic_analysis,
            "global_analysis": self.global_analysis,
            "information_gap": self.information_gap,
            "future_prediction": self.future_prediction,
            "opportunities": self.opportunities,
        }


class TrendAnalyzer:
    """Analyze high-value articles and produce trend intelligence."""

    def __init__(
        self,
        provider: AIProvider,
        config_path: Path = DEFAULT_TREND_CONFIG,
    ) -> None:
        self._provider = provider
        self._config = self._load_config(config_path)
        self._analysis_count = int(self._config.get("analysis_count", 10))

    @property
    def analysis_count(self) -> int:
        """Return the configured number of articles to analyze."""

        return self._analysis_count

    def analyze(self, items: Sequence[ReportItem]) -> TrendAnalysis:
        """Analyze scored articles and return TrendAnalysis."""

        payload = [
            {
                "title": item.article_title,
                "category": item.category,
                "importance_score": item.importance,
                "summary": item.summary,
                "link": item.article_link,
            }
            for item in list(items)[: self._analysis_count]
        ]
        prompt = self._build_prompt(payload)
        if hasattr(self._provider, "complete"):
            content = self._provider.complete(prompt)
        else:
            content = self._provider.analyze(prompt).summary
        return self._parse(content)

    def _build_prompt(self, payload: list[dict[str, Any]]) -> str:
        system_prompt = str(self._config.get("system_prompt", ""))
        output_format = str(self._config.get("output_format", ""))
        style_guidelines = "\n".join(
            f"- {item}"
            for item in self._config.get("style_guidelines", [])
        )
        rules = "\n".join(
            f"- {rule}" for rule in self._config.get("rules", [])
        )
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        return (
            f"{system_prompt}\n\n"
            f"输出风格：\n{style_guidelines}\n\n"
            f"输出格式：\n{output_format}\n\n"
            f"规则：\n{rules}\n\n"
            f"数据：\n{data}\n\n"
            "请把趋势分析结果放在 AnalysisResult 的 summary 字段中，"
            "内容必须是合法的 JSON 字符串。"
        )

    @staticmethod
    def _parse(content: str) -> TrendAnalysis:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise TrendAnalysisError(
                "Trend analysis output is not valid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise TrendAnalysisError(
                "Trend analysis output must be a JSON object"
            )
        try:
            return TrendAnalysis(
                major_trends=data["major_trends"],
                domestic_analysis=data["domestic_analysis"],
                global_analysis=data["global_analysis"],
                information_gap=data["information_gap"],
                future_prediction=data["future_prediction"],
                opportunities=data["opportunities"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TrendAnalysisError(
                f"Invalid trend analysis fields: {exc}"
            ) from exc

    @staticmethod
    def _load_config(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise TrendAnalysisError(
                f"Trend config file not found: {path}"
            )
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise TrendAnalysisError(
                f"Invalid trend YAML in {path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise TrendAnalysisError(
                f"Trend config must be a mapping: {path}"
            )
        return data
