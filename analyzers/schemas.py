"""Data schemas for AI analysis results.

Defines the contract that future AI provider adapters (DeepSeek, OpenAI,
Claude, etc.) will fill.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnalysisResult:
    """Normalized output of an AI analysis for one article."""

    importance: int
    category: str
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    impact: str = ""
    action: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.importance, int) or not 1 <= self.importance <= 10:
            raise ValueError("importance must be an integer between 1 and 10")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string")
        if not isinstance(self.tags, list) or not all(
            isinstance(tag, str) and tag.strip() for tag in self.tags
        ):
            raise ValueError("tags must be a list of non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result for JSON-compatible provider output."""

        return asdict(self)
