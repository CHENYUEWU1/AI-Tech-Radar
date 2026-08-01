from __future__ import annotations

import json

import pytest

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult
from analyzers.trend_analyzer import (
    DEFAULT_TREND_CONFIG,
    TrendAnalysisError,
    TrendAnalyzer,
)
from reports.data_aggregator import ReportItem


class FakeProvider(AIProvider):
    """Provider that returns a fixed AnalysisResult."""

    def __init__(self, summary: str) -> None:
        self._summary = summary

    def analyze(self, article: str) -> AnalysisResult:
        return AnalysisResult(
            importance=8,
            category="trend",
            tags=["trend"],
            summary=self._summary,
        )

    def complete(self, prompt: str) -> str:
        return self._summary


def _trend_payload() -> dict[str, object]:
    return {
        "major_trends": ["AI Agent", "MCP"],
        "domestic_analysis": "国内长鑫与芯片进展加速。",
        "global_analysis": "全球 GPU 需求持续增长。",
        "information_gap": "显卡价格与渠道信息不透明。",
        "future_prediction": "Agent 生态将加速落地。",
        "opportunities": ["Agent 工具链", "存储芯片"],
    }


def _item() -> ReportItem:
    return ReportItem(
        result=AnalysisResult(
            importance=9,
            category="AI",
            tags=["Agent"],
            summary="Summary.",
            impact="Impact.",
            action="Action.",
        ),
        article_title="Agent framework release",
        article_link="https://example.com/1",
        article_summary="A new MCP agent.",
        article_content="A new MCP agent.",
    )


def test_trend_analyzer_returns_trend_analysis() -> None:
    payload = _trend_payload()
    provider = FakeProvider(json.dumps(payload, ensure_ascii=False))
    analyzer = TrendAnalyzer(provider, config_path=DEFAULT_TREND_CONFIG)

    trend = analyzer.analyze([_item()])

    assert trend.major_trends == ["AI Agent", "MCP"]
    assert "长鑫" in trend.domestic_analysis
    assert set(trend.to_dict()) == {
        "major_trends",
        "domestic_analysis",
        "global_analysis",
        "information_gap",
        "future_prediction",
        "opportunities",
    }


def test_trend_analyzer_invalid_json_raises() -> None:
    analyzer = TrendAnalyzer(
        FakeProvider("not-json"), config_path=DEFAULT_TREND_CONFIG
    )

    with pytest.raises(TrendAnalysisError, match="not valid JSON"):
        analyzer.analyze([_item()])


def test_trend_analyzer_config_count() -> None:
    analyzer = TrendAnalyzer(
        FakeProvider("{}"), config_path=DEFAULT_TREND_CONFIG
    )

    assert analyzer.analysis_count == 10
