"""Daily report pipeline.

Coordinates report data aggregation and Markdown generation without
creating database connections or AI providers.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reports.data_aggregator import ReportDataAggregator, ReportDataError
from reports.markdown_generator import (
    MarkdownReportError,
    MarkdownReportGenerator,
)
from utils.logger import logger


class ReportPipelineError(Exception):
    """Raised when the daily report pipeline fails."""


class ReportPipeline:
    """Run the complete daily report generation flow."""

    def __init__(
        self,
        aggregator: ReportDataAggregator,
        generator: MarkdownReportGenerator,
    ) -> None:
        self._aggregator = aggregator
        self._generator = generator

    def generate_daily_report(
        self,
        report_date: date | None = None,
        limit: int = 10,
        output_dir: Path | None = None,
    ) -> Path:
        """Generate and save a daily report.

        Args:
            report_date: Date used for the report filename.
            limit: Maximum number of analyses to include.
            output_dir: Output directory override for testing.

        Returns:
            The path of the saved Markdown report.

        Raises:
            ReportPipelineError: If aggregation, generation, or saving fails.
        """

        try:
            results = self._aggregator.get_daily_analysis(limit=limit)
        except ReportDataError as exc:
            logger.error("Failed to load daily analysis: {}", exc)
            raise ReportPipelineError(
                f"Failed to load daily analysis: {exc}"
            ) from exc

        if not results:
            raise ReportPipelineError(
                "No analysis data in the last 24 hours"
            )

        try:
            markdown = self._generator.generate(results)
            path = self._generator.save_report(
                markdown,
                report_date=report_date,
                output_dir=output_dir,
            )
        except MarkdownReportError as exc:
            logger.error("Failed to generate daily report: {}", exc)
            raise ReportPipelineError(
                f"Failed to generate daily report: {exc}"
            ) from exc

        logger.info("Daily report saved to {}", path)
        return path
