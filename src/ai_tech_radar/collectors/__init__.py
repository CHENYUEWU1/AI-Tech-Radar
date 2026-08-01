"""Collectors that turn external sources into CollectedItem objects."""

from ai_tech_radar.collectors.base import CollectedItem, Collector
from ai_tech_radar.collectors.github import GitHubCollector
from ai_tech_radar.collectors.rss import RSSCollector
from ai_tech_radar.collectors.twitter import TwitterCollector

__all__ = [
    "CollectedItem",
    "Collector",
    "GitHubCollector",
    "RSSCollector",
    "TwitterCollector",
]
