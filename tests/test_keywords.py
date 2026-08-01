from __future__ import annotations

from ai_tech_radar.analyzers.keywords import KeywordAnalyzer
from ai_tech_radar.config import KeywordConfig
from ai_tech_radar.models import Priority


def _analyzer() -> KeywordAnalyzer:
    return KeywordAnalyzer(
        KeywordConfig(
            high_priority=("Agent", "MCP", "OpenAI"),
            medium_priority=("GPU",),
            low_priority=("VR",),
        )
    )


def test_keyword_priority_and_score() -> None:
    result = _analyzer().analyze(
        "OpenAI released an Agent with MCP support and GPU training plus VR demos"
    )

    assert result.priority == Priority.HIGH
    assert result.score == 12
    assert result.keywords == {
        "Agent": 1,
        "MCP": 1,
        "OpenAI": 1,
        "GPU": 1,
        "VR": 1,
    }


def test_no_keywords_gives_none_priority() -> None:
    result = _analyzer().analyze("A quiet update with no matching terms")

    assert result.priority == Priority.NONE
    assert result.score == 0
    assert result.keywords == {}
