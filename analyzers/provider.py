"""AI provider abstraction layer.

Defines the unified interface that concrete providers such as DeepSeek,
OpenAI, Claude, and local LLMs will implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from analyzers.schemas import AnalysisResult


class AIProvider(ABC):
    """Unified interface for AI model providers.

    Future implementations:
    - DeepSeek
    - OpenAI
    - Claude
    - Local LLM
    """

    @abstractmethod
    def analyze(self, article: str) -> AnalysisResult:
        """Analyze an article and return a structured result.

        Args:
            article: Raw article text to analyze.

        Returns:
            AnalysisResult containing importance, category, tags,
            summary, impact, and action fields.
        """
