"""Priority keyword scoring for collected articles."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_tech_radar.config import KeywordConfig
from ai_tech_radar.models import Priority


@dataclass(frozen=True)
class KeywordResult:
    """Result of keyword analysis for one article."""

    score: int
    priority: Priority
    keywords: dict[str, int]


class KeywordAnalyzer:
    """Score text against configured high/medium/low priority keywords."""

    def __init__(self, config: KeywordConfig) -> None:
        self._groups: list[tuple[Priority, int, tuple[str, ...]]] = [
            (Priority.HIGH, 3, config.high_priority),
            (Priority.MEDIUM, 2, config.medium_priority),
            (Priority.LOW, 1, config.low_priority),
        ]
        self._patterns: list[tuple[Priority, int, str, re.Pattern[str]]] = []
        for priority, weight, keywords in self._groups:
            for keyword in keywords:
                self._patterns.append(
                    (priority, weight, keyword, _keyword_pattern(keyword))
                )

    def analyze(self, text: str) -> KeywordResult:
        """Count keyword matches and compute priority and score."""

        counts: dict[str, int] = {}
        matched_priority = Priority.NONE
        score = 0
        for priority, weight, keyword, pattern in self._patterns:
            count = len(pattern.findall(text))
            if count == 0:
                continue
            counts[keyword] = counts.get(keyword, 0) + count
            score += count * weight
            if matched_priority == Priority.NONE:
                matched_priority = priority
        return KeywordResult(score=score, priority=matched_priority, keywords=counts)


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])",
        re.IGNORECASE,
    )
