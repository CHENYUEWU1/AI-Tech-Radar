from __future__ import annotations

from analyzers.analyzer import AIAnalyzer
from analyzers.mock_provider import MockProvider
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


class RecordingProvider(AIProvider):
    """Test provider that records the article it receives."""

    def __init__(self) -> None:
        self.received_article: str | None = None

    def analyze(self, article: str) -> AnalysisResult:
        self.received_article = article
        return AnalysisResult(
            importance=6,
            category="LLM",
            tags=["Agent"],
            summary="Test summary.",
            impact="Test impact.",
            action="Test action.",
        )


def test_analyzer_delegates_to_provider() -> None:
    provider = RecordingProvider()
    analyzer = AIAnalyzer(provider)

    result = analyzer.analyze("A new LLM paper was published.")

    assert provider.received_article == "A new LLM paper was published."
    assert result.category == "LLM"
    assert result.tags == ["Agent"]


def test_analyzer_works_with_mock_provider() -> None:
    analyzer = AIAnalyzer(MockProvider())

    result = analyzer.analyze("任意文章内容")

    assert isinstance(result, AnalysisResult)
    assert result.category == "AI"
    assert result.tags == ["LLM", "Agent"]


def test_analyzer_returns_analysis_result() -> None:
    provider = MockProvider()
    analyzer = AIAnalyzer(provider)

    result = analyzer.analyze("OpenAI released a new model")

    assert isinstance(result, AnalysisResult)
    assert 1 <= result.importance <= 10
    assert result.category == "AI"
    assert result.tags == ["LLM", "Agent"]
