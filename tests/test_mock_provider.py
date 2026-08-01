from __future__ import annotations

from analyzers.mock_provider import MockProvider
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


def test_mock_provider_is_ai_provider() -> None:
    assert isinstance(MockProvider(), AIProvider)


def test_mock_provider_returns_fixed_result() -> None:
    result = MockProvider().analyze("任意文章内容")

    assert isinstance(result, AnalysisResult)
    assert 1 <= result.importance <= 10
    assert result.category == "AI"
    assert result.tags == ["LLM", "Agent"]
    assert result.summary == "模拟摘要"
    assert result.impact == "模拟影响分析"
    assert result.action == "模拟关注建议"


def test_mock_provider_result_is_identical_across_calls() -> None:
    provider = MockProvider()

    assert provider.analyze("article A") == provider.analyze("article B")
