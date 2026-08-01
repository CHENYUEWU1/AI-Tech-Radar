from __future__ import annotations

import feedparser

from ai_tech_radar.collectors.rss import RSSCollector
from ai_tech_radar.config import RSSSourceConfig


_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
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


def test_rss_entry_to_item() -> None:
    source = RSSSourceConfig(
        name="Test Feed", category="ai_company", url="https://example.com/rss"
    )
    entry = feedparser.parse(_SAMPLE_FEED).entries[0]

    item = RSSCollector._entry_to_item(source, entry)

    assert item.external_id == "post-1"
    assert item.title == "Agent MCP update"
    assert item.url == "https://example.com/post/1"
    assert item.author == "Ada"
    assert item.published_at is not None
    assert item.kind.value == "rss"
