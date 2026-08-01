"""Markdown daily report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ai_tech_radar.analyzers.trends import TrendItem
from ai_tech_radar.exceptions import ReportError
from ai_tech_radar.models import AnalyzedArticle


class DailyReporter:
    """Render a daily Markdown report and write it under reports/."""

    def render(
        self,
        report_date: str,
        articles: Sequence[AnalyzedArticle],
        trends: Sequence[TrendItem],
        stats: dict[str, Any],
    ) -> str:
        """Build the Markdown document."""

        lines = [
            f"# AI Tech Radar - {report_date}",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC",
            "",
            "## Summary",
            f"- New articles: {stats.get('articles', 0)}",
            f"- Analyzed: {stats.get('analyzed', 0)}",
            f"- Sources: {stats.get('sources', 0)}",
            f"- Categories: {', '.join(stats.get('categories', {})) or 'none'}",
            "",
            "## Top Keywords",
        ]
        if trends:
            lines.append("| Keyword | Mentions | Articles |")
            lines.append("| --- | ---: | ---: |")
            for trend in trends:
                lines.append(
                    f"| {trend.keyword} | {trend.mentions} | {trend.articles} |"
                )
        else:
            lines.append("No keywords matched in this window.")

        lines.extend(["", "## Top Articles"])
        if articles:
            for index, article in enumerate(articles, start=1):
                lines.extend(self._article_section(index, article))
        else:
            lines.append("No scored articles in this window.")
        return "\n".join(lines) + "\n"

    def write(
        self, report_date: str, content: str, report_dir: Path
    ) -> Path:
        """Write the report and return its path."""

        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            path = report_dir / f"{report_date}.md"
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ReportError(f"Cannot write report {path}: {exc}") from exc
        return path

    @staticmethod
    def _article_section(index: int, article: AnalyzedArticle) -> list[str]:
        published = (
            article.published_at.isoformat(timespec="seconds")
            if article.published_at is not None
            else "unknown"
        )
        summary = " ".join(article.summary.split()) or "No summary available."
        return [
            f"### {index}. {article.title}",
            f"- Source: {article.source_name} ({article.category})",
            f"- Priority: {article.priority}",
            f"- Published: {published}",
            f"- Score: {article.score}",
            "",
            summary,
            "",
            f"[Read more]({article.url})",
            "",
            "---",
            "",
        ]
