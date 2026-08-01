"""Mock AI provider for testing the analysis pipeline.

This is a test provider and will be replaced by real providers such as
DeepSeek or OpenAI in the future.
"""

from __future__ import annotations

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


class MockProvider(AIProvider):
    """Return a fixed AnalysisResult without calling any external API."""

    def analyze(self, article: str) -> AnalysisResult:
        """Analyze an article and return the fixed mock result.

        Args:
            article: Article text; kept for interface compatibility.

        Returns:
            A fixed AnalysisResult for testing.
        """

        return AnalysisResult(
            importance=8,
            category="AI",
            tags=["LLM", "Agent"],
            summary="模拟摘要",
            impact="模拟影响分析",
            action="模拟关注建议",
        )
