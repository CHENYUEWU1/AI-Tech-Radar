from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from analyzers.analyzer import AIAnalyzer
from analyzers.provider import AIProvider
from analyzers.schemas import AnalysisResult
from reports.markdown_generator import (
    DEFAULT_PROMPT_PATH,
    MarkdownReportError,
    MarkdownReportGenerator,
)


class ReportProvider(AIProvider):
    """Provider that records the prompt and returns fixed Markdown."""

    def __init__(self, markdown: str = "# AI Tech Radar Daily\n\n## 今日重点") -> None:
        self.prompt = ""
        self._markdown = markdown

    def analyze(self, article: str) -> AnalysisResult:
        self.prompt = article
        return AnalysisResult(
            importance=1,
            category="report",
            tags=["daily"],
            summary=self._markdown,
        )


def _result() -> AnalysisResult:
    return AnalysisResult(
        importance=8,
        category="AI",
        tags=["LLM", "Agent"],
        summary="Summary.",
        impact="Impact.",
        action="Action.",
    )


def test_generate_returns_markdown() -> None:
    provider = ReportProvider()
    generator = MarkdownReportGenerator(
        AIAnalyzer(provider), prompt_config=DEFAULT_PROMPT_PATH
    )

    markdown = generator.generate([_result()])

    assert "# AI Tech Radar Daily" in markdown
    assert "## 今日重点" in markdown
    assert '"importance"' in provider.prompt
    assert '"category"' in provider.prompt


def test_generate_empty_report_raises() -> None:
    provider = ReportProvider(markdown="   ")
    generator = MarkdownReportGenerator(
        AIAnalyzer(provider), prompt_config=DEFAULT_PROMPT_PATH
    )

    with pytest.raises(MarkdownReportError, match="empty report"):
        generator.generate([_result()])


def test_save_report_writes_date_named_file(tmp_path: Path) -> None:
    generator = MarkdownReportGenerator(
        AIAnalyzer(ReportProvider()), prompt_config=DEFAULT_PROMPT_PATH
    )

    path = generator.save_report(
        "# AI Tech Radar Daily",
        report_date=date(2026, 8, 1),
        output_dir=tmp_path,
    )

    assert path.name == "2026-08-01-ai-tech-radar.md"
    assert path.read_text(encoding="utf-8") == "# AI Tech Radar Daily"


def test_missing_prompt_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MarkdownReportError, match="not found"):
        MarkdownReportGenerator(
            AIAnalyzer(ReportProvider()),
            prompt_config=tmp_path / "missing.yaml",
        )
