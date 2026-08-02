from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from collectors.twitter_collector import (
    TwitterCollectionError,
    TwitterCollector,
)
from utils.config_loader import ConfigError


def _write_config(config_dir: Path, twitter_yaml: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "sources.yaml").write_text(twitter_yaml, encoding="utf-8")


def _tweet(tweet_id: str = "123", text: str = "New agent framework is out") -> dict[str, Any]:
    return {
        "id": tweet_id,
        "text": text,
        "created_at": "2026-08-01T08:00:00.000Z",
        "author_id": "42",
    }


def test_tweet_to_item_conversion() -> None:
    source = TwitterCollector._parse_source(
        {"username": "OpenAI", "category": "ai_company", "enabled": True}
    )

    item = TwitterCollector._tweet_to_item(source, _tweet())

    assert item.external_id == "tweet-123"
    assert item.title == "New agent framework is out"
    assert item.link == "https://x.com/OpenAI/status/123"
    assert item.author == "OpenAI"
    assert item.source_name == "OpenAI"
    assert item.category == "ai_company"
    assert item.published_at == datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def test_tweet_title_is_truncated() -> None:
    source = TwitterCollector._parse_source("OpenAI")
    long_text = "word " * 200

    item = TwitterCollector._tweet_to_item(source, _tweet(text=long_text))

    assert len(item.title) <= 120
    assert item.title.endswith("...")


def test_collect_without_token_uses_rsshub_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
twitter:
  - username: OpenAI
    category: ai_company
    enabled: true
""",
    )
    collector = TwitterCollector(config_dir=config_dir, token=None)
    monkeypatch.setenv("X_BEARER_TOKEN", "")
    monkeypatch.setattr(
        collector,
        "_fetch_rsshub_entries",
        lambda username: [
            {
                "title": "OpenAI: New model released",
                "link": "https://twitter.com/OpenAI/status/777",
                "summary": "<p>Fresh <b>agent</b> news</p>",
                "published_parsed": None,
            }
        ],
    )

    items = collector.collect()

    assert len(items) == 1
    assert items[0].external_id == "tweet-777"
    assert items[0].title == "OpenAI: New model released"
    assert items[0].summary == "Fresh agent news"
    assert items[0].source_name == "OpenAI"
    assert collector.failure_count == 0


def test_rsshub_mode_continues_after_account_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
twitter:
  - username: OpenAI
    category: ai_company
    enabled: true
  - username: broken
    category: community
    enabled: true
""",
    )
    collector = TwitterCollector(config_dir=config_dir, token=None)
    monkeypatch.setenv("X_BEARER_TOKEN", "")

    def fake_fetch(username: str) -> list[dict[str, Any]]:
        if username == "broken":
            raise TwitterCollectionError("all instances failed")
        return [
            {
                "title": "OpenAI: update",
                "link": "https://twitter.com/OpenAI/status/1",
                "summary": "",
            }
        ]

    monkeypatch.setattr(collector, "_fetch_rsshub_entries", fake_fetch)

    items = collector.collect()

    assert [item.external_id for item in items] == ["tweet-1"]
    assert collector.failure_count == 1


def test_rsshub_mode_returns_empty_when_all_instances_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
twitter:
  - username: OpenAI
    category: ai_company
    enabled: true
""",
    )
    collector = TwitterCollector(config_dir=config_dir, token=None)
    monkeypatch.setenv("X_BEARER_TOKEN", "")

    def fake_fetch(username: str) -> list[dict[str, Any]]:
        raise TwitterCollectionError("all instances failed")

    monkeypatch.setattr(collector, "_fetch_rsshub_entries", fake_fetch)

    assert collector.collect() == []
    assert collector.failure_count == 1


def test_collect_fetches_tweets_for_each_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
twitter:
  - username: OpenAI
    category: ai_company
    enabled: true
  - username: deepseek_ai
    category: models
    enabled: true
""",
    )
    collector = TwitterCollector(config_dir=config_dir, token="test-token")
    monkeypatch.setattr(
        collector,
        "_lookup_users",
        lambda client, sources: {
            "openai": "1",
            "deepseek_ai": "2",
        },
    )
    monkeypatch.setattr(
        collector,
        "_user_tweets",
        lambda client, user_id: [_tweet(tweet_id=user_id)],
    )

    items = collector.collect()

    assert len(items) == 2
    assert {item.source_name for item in items} == {"OpenAI", "deepseek_ai"}
    assert {item.external_id for item in items} == {"tweet-1", "tweet-2"}
    assert collector.failure_count == 0


def test_collect_continues_after_account_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
twitter:
  - username: OpenAI
    category: ai_company
    enabled: true
  - username: broken
    category: community
    enabled: true
""",
    )
    collector = TwitterCollector(config_dir=config_dir, token="test-token")
    monkeypatch.setattr(
        collector,
        "_lookup_users",
        lambda client, sources: {"openai": "1", "broken": "2"},
    )

    def fake_tweets(client: Any, user_id: str) -> list[dict[str, Any]]:
        if user_id == "2":
            raise TwitterCollectionError("rate limited")
        return [_tweet(tweet_id=user_id)]

    monkeypatch.setattr(collector, "_user_tweets", fake_tweets)

    items = collector.collect()

    assert [item.external_id for item in items] == ["tweet-1"]
    assert collector.failure_count == 1


def test_invalid_twitter_section_raises(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir, "twitter: not-a-list\n")

    with pytest.raises(ConfigError, match="must be a list"):
        TwitterCollector(config_dir=config_dir, token="test-token").collect()
