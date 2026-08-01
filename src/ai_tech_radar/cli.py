"""Command-line interface for AI Tech Radar."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Sequence

from loguru import logger

from ai_tech_radar.config import load_keywords, load_settings, load_sources
from ai_tech_radar.database import Database
from ai_tech_radar.exceptions import ConfigError, TechRadarError
from ai_tech_radar.log_setup import setup_logging
from ai_tech_radar.models import SourceKind
from ai_tech_radar.pipeline import Pipeline


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested command."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    config_dir = Path(args.config_dir).resolve()

    try:
        settings = load_settings(config_dir)
        sources = load_sources(config_dir)
        keywords = load_keywords(config_dir)
        setup_logging(settings.log_dir, args.log_level)
    except TechRadarError as exc:
        logger.error("Configuration error: {}", exc)
        return 1

    pipeline = Pipeline(settings, sources, keywords)
    try:
        if args.command == "init":
            with Database(settings.database_path) as db:
                logger.info("Initialized database at {}", db.path)
        elif args.command == "collect":
            summary = pipeline.collect(
                _parse_kinds(args.sources), limit=args.limit
            )
            logger.info(
                "Collected {} items, inserted {} new",
                summary.total,
                summary.inserted,
            )
        elif args.command == "analyze":
            analyzed = pipeline.analyze(args.limit)
            logger.info("Analyzed {} articles", analyzed)
        elif args.command == "report":
            path = pipeline.report(
                report_date=_parse_date(args.date),
                days=args.days,
                min_score=args.min_score,
            )
            logger.info("Report written to {}", path)
        elif args.command == "run":
            result = pipeline.run(
                kinds=_parse_kinds(args.sources),
                analyze_limit=args.analyze_limit,
                report_date=_parse_date(args.date),
                days=args.days,
                min_score=args.min_score,
                collect_limit=args.limit,
            )
            logger.info(
                "Pipeline finished: {} items, {} analyzed, report at {}",
                result.collected.total,
                result.analyzed,
                result.report_path,
            )
    except TechRadarError as exc:
        logger.error("Command failed: {}", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected failure: {}", exc)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-tech-radar",
        description="Collect, analyze, and report on AI technology intelligence.",
    )
    parser.add_argument("--config-dir", default="config", help="Path to config/")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the database")
    init_parser.set_defaults(command="init")

    collect_parser = subparsers.add_parser(
        "collect", help="Collect articles from configured sources"
    )
    collect_parser.add_argument(
        "--sources", help="Comma-separated kinds: rss,github,twitter"
    )
    collect_parser.add_argument(
        "--limit", type=int, default=0, help="Per-source item limit override"
    )
    collect_parser.set_defaults(command="collect")

    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze collected articles without an analysis"
    )
    analyze_parser.add_argument(
        "--limit", type=int, default=200, help="Maximum articles to analyze"
    )
    analyze_parser.set_defaults(command="analyze")

    report_parser = subparsers.add_parser(
        "report", help="Generate a Markdown daily report"
    )
    report_parser.add_argument("--date", help="Report date as YYYY-MM-DD")
    report_parser.add_argument("--days", type=int, default=1)
    report_parser.add_argument("--min-score", type=int, default=1)
    report_parser.set_defaults(command="report")

    run_parser = subparsers.add_parser(
        "run", help="Run collect, analyze, and report"
    )
    run_parser.add_argument(
        "--sources", help="Comma-separated kinds: rss,github,twitter"
    )
    run_parser.add_argument(
        "--limit", type=int, default=0, help="Per-source item limit override"
    )
    run_parser.add_argument("--analyze-limit", type=int, default=200)
    run_parser.add_argument("--date", help="Report date as YYYY-MM-DD")
    run_parser.add_argument("--days", type=int, default=1)
    run_parser.add_argument("--min-score", type=int, default=1)
    run_parser.set_defaults(command="run")
    return parser


def _parse_kinds(raw: str | None) -> list[SourceKind] | None:
    if not raw:
        return None
    kinds: list[SourceKind] = []
    for part in raw.split(","):
        token = part.strip().lower()
        try:
            kinds.append(SourceKind(token))
        except ValueError as exc:
            raise ConfigError(f"Unknown source kind: {token}") from exc
    return kinds


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid date '{raw}', expected YYYY-MM-DD") from exc
