"""AI analysis orchestrator.

AIAnalyzer coordinates the analysis flow and does not care about the
concrete AI model implementation.
"""

from __future__ import annotations

from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult


class AIAnalyzer:
    """Coordinate article analysis through an injected AIProvider."""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def analyze(self, article: str) -> AnalysisResult:
        """Analyze an article using the configured provider.

        Args:
            article: Raw article text to analyze.

        Returns:
            AnalysisResult produced by the provider.
        """

        return self._provider.analyze(article)
