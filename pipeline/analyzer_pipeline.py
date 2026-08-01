"""AI analysis pipeline.

Orchestrates AIAnalyzer and AnalysisRepository without creating its own
provider or database connection.
"""

from __future__ import annotations

from analyzers.analyzer import AIAnalyzer
from analyzers.schemas import AnalysisResult
from database.analysis_repository import (
    AnalysisRepository,
    AnalysisRepositoryError,
)
from utils.logger import logger


class AnalyzerPipelineError(Exception):
    """Raised when the analysis pipeline fails."""


class AnalyzerPipeline:
    """Run one article through analysis and persist the result."""

    def __init__(
        self,
        analyzer: AIAnalyzer,
        repository: AnalysisRepository,
    ) -> None:
        self._analyzer = analyzer
        self._repository = repository

    def analyze_article(
        self,
        article_id: int,
        content: str,
        model: str = "unknown",
    ) -> AnalysisResult:
        """Analyze article content and save the result.

        Args:
            article_id: Database id of the article.
            content: Article text to analyze.
            model: Model name to record; defaults to "unknown".

        Returns:
            The AnalysisResult produced by the analyzer.

        Raises:
            AnalyzerPipelineError: If analysis or persistence fails.
        """

        try:
            result = self._analyzer.analyze(content)
        except Exception as exc:
            logger.error("AI analysis failed: {}", exc)
            raise AnalyzerPipelineError(
                f"AI analysis failed: {exc}"
            ) from exc

        try:
            self._repository.save(article_id, result, model)
        except AnalysisRepositoryError as exc:
            logger.error(
                "Failed to save analysis for article {}: {}",
                article_id,
                exc,
            )
            raise AnalyzerPipelineError(
                f"Failed to save analysis result: {exc}"
            ) from exc

        return result
