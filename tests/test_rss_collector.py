from __future__ import annotations

from pathlib import Path

import feedparser
import pytest

from collectors.rss_collector import RSSCollector, RSSItem, RSSSource
from utils.config_loader import ConfigError


SAMPLE_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Agent MCP update</title>
      <link>https://example.com/post/1</link>
      <guid>post-1</guid>
      <description>A new Agent release.</description>
      <author>Ada</author>
      <pubDate>Fri, 31 Jul 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def _write_config(config_dir: Path, rss_yaml: str) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "sources.yaml").write_text(rss_yaml, encoding="utf-8")


def test_entry_to_item() -> None:
    source = RSSSource(
        name="Test Feed", category="ai_company", url="https://example.com/rss"
    )
    entry = feedparser.parse(SAMPLE_FEED).entries[0]

    item = RSSCollector._entry_to_item(source, entry)

    assert item.external_id == "post-1"
    assert item.title == "Agent MCP update"
    assert item.link == "https://example.com/post/1"
    assert item.author == "Ada"
    assert item.published_at is not None


def test_collect_handles_failures_and_disabled_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
rss:
  - name: Good Feed
    category: ai_company
    url: https://example.com/ok
    enabled: true
  - name: Broken Feed
    category: community
    url: https://example.com/broken
    enabled: true
  - name: Disabled Feed
    category: models
    url: https://example.com/disabled
    enabled: false
""",
    )
    collector = RSSCollector(config_dir=config_dir, timeout_seconds=1, limit=10)

    def fake_fetch(url: str) -> bytes:
        if "broken" in url:
            raise RuntimeError("network failure")
        return SAMPLE_FEED

    monkeypatch.setattr(collector, "_fetch", fake_fetch)

    items = collector.collect()

    assert len(items) == 1
    assert items[0].source_name == "Good Feed"


def test_empty_feed_returns_no_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    _write_config(
        config_dir,
        """
rss:
  - name: Empty Feed
    category: ai_company
    url: https://example.com/empty
""",
    )
    collector = RSSCollector(config_dir=config_dir)
    monkeypatch.setattr(collector, "_fetch", lambda _url: b"<rss></rss>")

    assert collector.collect() == []


def test_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        RSSCollector(config_dir=tmp_path / "missing").collect()


def test_invalid_rss_section_raises(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir, "rss: not-a-list\n")

    with pytest.raises(ConfigError, match="must be a list"):
        RSSCollector(config_dir=config_dir).collect()


def test_format_item() -> None:
    item = RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title="Agent MCP update",
        link="https://example.com/post/1",
        summary="A new release.",
        author="Ada",
        published_at=None,
        external_id="post-1",
    )

    output = RSSCollector.format_item(item)

    assert "Test Feed" in output
    assert "Agent MCP update" in output
    assert "https://example.com/post/1" in output
