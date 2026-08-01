"""Shared collector helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware datetime."""

    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def truncate(text: str, limit: int = 160) -> str:
    """Truncate text to a readable summary length."""

    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."
