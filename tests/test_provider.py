from __future__ import annotations

import pytest

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


def test_abstract_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        AIProvider()


def test_concrete_provider_must_return_analysis_result() -> None:
    class FakeProvider(AIProvider):
        def analyze(self, article: str) -> AnalysisResult:
            return AnalysisResult(
                importance=7,
                category="LLM",
                tags=["Agent"],
                summary=f"Analyzed: {article}",
                impact="Lower agent development cost.",
                action="Track API and ecosystem updates.",
            )

    provider = FakeProvider()
    result = provider.analyze("A new agent framework was released.")

    assert isinstance(result, AnalysisResult)
    assert result.importance == 7
    assert result.category == "LLM"
    assert result.tags == ["Agent"]
