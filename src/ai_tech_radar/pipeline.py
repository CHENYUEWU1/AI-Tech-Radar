"""Orchestration for collect -> analyze -> report."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Sequence

from loguru import logger

from ai_tech_radar.analyzers.keywords import KeywordAnalyzer
from ai_tech_radar.analyzers.trends import TrendAnalyzer
from ai_tech_radar.collectors import (
    Collector,
    GitHubCollector,
    RSSCollector,
    TwitterCollector,
)
from ai_tech_radar.config import AppSettings, KeywordConfig, SourceConfig
from ai_tech_radar.database import Database
from ai_tech_radar.models import SourceKind, SourceRecord
from ai_tech_radar.reporters.daily import DailyReporter


@dataclass(frozen=True)
class CollectionSummary:
    """Collection run totals."""

    total: int
    inserted: int


@dataclass(frozen=True)
class PipelineResult:
    """Result of a full pipeline run."""

    collected: CollectionSummary
    analyzed: int
    report_path: Path


class Pipeline:
    """Coordinate collectors, storage, analysis, and reporting."""

    def __init__(
        self,
        settings: AppSettings,
        sources: SourceConfig,
        keywords: KeywordConfig,
    ) -> None:
        self._settings = settings
        self._sources = sources
        self._keywords = keywords

    def collect(
        self,
        kinds: Sequence[SourceKind] | None = None,
        limit: int | None = None,
    ) -> CollectionSummary:
        """Collect from selected source kinds and store new articles."""

        selected = set(kinds) if kinds else set(SourceKind)
        collectors = self._build_collectors(limit)
        source_records = self._source_records()
        total = 0
        inserted = 0

        with Database(self._settings.database_path) as db:
            db.upsert_sources(source_records)
            source_ids = db.source_id_map()
            now = datetime.now(timezone.utc)
            for collector in collectors:
                if collector.kind not in selected:
                    continue
                items = collector.collect()
                total += len(items)
                inserted += db.insert_articles(items, source_ids)
                keys = self._enabled_keys(collector)
                if keys:
                    db.mark_sources_collected(keys, now)
            logger.info(
                "Collection finished: {} items fetched, {} new stored",
                total,
                inserted,
            )
        return CollectionSummary(total=total, inserted=inserted)

    def analyze(self, limit: int = 200) -> int:
        """Run keyword analysis on collected articles without an analysis."""

        analyzer = KeywordAnalyzer(self._keywords)
        analyzed = 0
        with Database(self._settings.database_path) as db:
            articles = db.list_unanalyzed_articles(limit)
            for article in articles:
                text = " ".join([article.title, article.summary, article.content])
                result = analyzer.analyze(text)
                db.save_analysis(
                    article.id, result.score, result.priority, result.keywords
                )
                analyzed += 1
            logger.info("Analysis finished: {} articles analyzed", analyzed)
        return analyzed

    def report(
        self,
        report_date: date | None = None,
        days: int = 1,
        min_score: int = 1,
        top_articles: int = 50,
    ) -> Path:
        """Generate and persist a Markdown daily report."""

        target = report_date or date.today()
        since = datetime.combine(target, time.min, tzinfo=timezone.utc)
        reporter = DailyReporter()
        trend_analyzer = TrendAnalyzer()

        with Database(self._settings.database_path) as db:
            articles = db.list_analyzed_articles(
                since=since, limit=top_articles, min_score=min_score
            )
            trends = trend_analyzer.analyze(articles)
            stats = {
                "articles": db.count_articles(since),
                "analyzed": db.count_analyzed(since),
                "sources": len(db.source_id_map()),
                "categories": db.category_counts(since),
            }
            content = reporter.render(target.isoformat(), articles, trends, stats)
            path = reporter.write(target.isoformat(), content, self._settings.report_dir)
            summary = f"{len(articles)} analyzed articles, {len(trends)} trends"
            db.save_report(target.isoformat(), path, summary)
            logger.info("Report written to {}", path)
        return path

    def run(
        self,
        kinds: Sequence[SourceKind] | None = None,
        analyze_limit: int = 200,
        report_date: date | None = None,
        days: int = 1,
        min_score: int = 1,
        collect_limit: int | None = None,
    ) -> PipelineResult:
        """Run the full collect -> analyze -> report pipeline."""

        collected = self.collect(kinds, limit=collect_limit)
        analyzed = self.analyze(analyze_limit)
        path = self.report(report_date, days=days, min_score=min_score)
        return PipelineResult(
            collected=collected, analyzed=analyzed, report_path=path
        )

    def _build_collectors(self, limit: int | None) -> list[Collector]:
        collectors_cfg = self._settings.collectors
        per_source_limit = limit or collectors_cfg.per_source_limit
        collectors: list[Collector] = []
        if self._sources.rss:
            collectors.append(
                RSSCollector(
                    self._sources.rss,
                    timeout_seconds=collectors_cfg.request_timeout_seconds,
                    limit=per_source_limit,
                )
            )
        if self._sources.github:
            collectors.append(
                GitHubCollector(
                    self._sources.github,
                    timeout_seconds=collectors_cfg.request_timeout_seconds,
                    per_repo_limit=collectors_cfg.github.per_repo_limit,
                    token=_env_token(collectors_cfg.github.token_env),
                )
            )
        if self._sources.twitter:
            collectors.append(
                TwitterCollector(
                    self._sources.twitter,
                    timeout_seconds=collectors_cfg.request_timeout_seconds,
                    per_user_limit=collectors_cfg.twitter.per_user_limit,
                    token=_env_token(collectors_cfg.twitter.token_env),
                )
            )
        return collectors

    def _source_records(self) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for source in self._sources.rss:
            records.append(
                SourceRecord(
                    kind=SourceKind.RSS,
                    name=source.name,
                    category=source.category,
                    url=source.url,
                    enabled=source.enabled,
                )
            )
        for source in self._sources.github:
            records.append(
                SourceRecord(
                    kind=SourceKind.GITHUB,
                    name=source.name,
                    category=source.category,
                    enabled=source.enabled,
                )
            )
        for source in self._sources.twitter:
            records.append(
                SourceRecord(
                    kind=SourceKind.TWITTER,
                    name=source.username,
                    category=source.category,
                    enabled=source.enabled,
                )
            )
        return records

    @staticmethod
    def _enabled_keys(collector: Collector) -> list[tuple[SourceKind, str]]:
        if isinstance(collector, RSSCollector):
            return [
                (SourceKind.RSS, source.name)
                for source in collector._sources
                if source.enabled
            ]
        if isinstance(collector, GitHubCollector):
            return [
                (SourceKind.GITHUB, source.name)
                for source in collector._sources
                if source.enabled
            ]
        if isinstance(collector, TwitterCollector):
            return [
                (SourceKind.TWITTER, source.username)
                for source in collector._sources
                if source.enabled
            ]
        return []


def _env_token(env_name: str) -> str | None:
    token = os.getenv(env_name, "").strip()
    return token or None
