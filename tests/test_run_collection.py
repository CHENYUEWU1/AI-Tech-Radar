from __future__ import annotations

from datetime import datetime, timezone

from collectors.rss_collector import RSSItem
from main import ApplicationComponents, run_collection


class FakeCollector:
    """Collector stub for run_collection tests."""

    def __init__(
        self,
        items: list[RSSItem] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._items = items or []
        self._error = error

    def collect(self) -> list[RSSItem]:
        if self._error is not None:
            raise self._error
        return self._items


class FakeDatabase:
    """Database stub that records saved articles."""

    def __init__(self, fail_external_ids: set[str] | None = None) -> None:
        self.saved: list[RSSItem] = []
        self._fail_external_ids = fail_external_ids or set()

    def save_article(self, item: RSSItem) -> bool:
        if item.external_id in self._fail_external_ids:
            raise RuntimeError("save failed")
        self.saved.append(item)
        return True


def _item(external_id: str = "post-1") -> RSSItem:
    return RSSItem(
        source_name="Test Feed",
        category="ai_company",
        title="Agent MCP update",
        link="https://example.com/post/1",
        summary="A new Agent release.",
        author="Ada",
        published_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
        external_id=external_id,
    )


def _components(
    collector: FakeCollector, database: FakeDatabase
) -> ApplicationComponents:
    return ApplicationComponents(
        database=database,
        collector=collector,
        analyzer=None,  # type: ignore[arg-type]
        report_pipeline=None,  # type: ignore[arg-type]
    )


def test_run_collection_saves_items() -> None:
    items = [_item("a"), _item("b")]
    database = FakeDatabase()
    components = _components(FakeCollector(items), database)

    saved = run_collection(components)

    assert saved == 2
    assert database.saved == items


def test_run_collection_collector_failure_does_not_crash() -> None:
    database = FakeDatabase()
    components = _components(
        FakeCollector(error=RuntimeError("network failure")), database
    )

    assert run_collection(components) == 0
    assert database.saved == []


def test_run_collection_save_failure_does_not_crash() -> None:
    database = FakeDatabase(fail_external_ids={"post-1"})
    components = _components(FakeCollector([_item()]), database)

    assert run_collection(components) == 0
    assert database.saved == []


def test_run_collection_continues_after_single_save_failure() -> None:
    database = FakeDatabase(fail_external_ids={"a"})
    components = _components(
        FakeCollector([_item("a"), _item("b")]), database
    )

    saved = run_collection(components)

    assert saved == 1
    assert [item.external_id for item in database.saved] == ["b"]
