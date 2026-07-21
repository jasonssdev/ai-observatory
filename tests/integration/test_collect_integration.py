"""End-to-end pipeline integration test: fetch -> parse -> dedup -> store -> render.

Uses two mocked sources whose feeds share one duplicate item (same canonical
URL, so same persistent id) to prove the full pipeline collapses it to a
single stored row and a single rendered Markdown line.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_observatory.cli import _write_daily_records, collect
from ai_observatory.collection.base import Source
from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.rss import RssCollector
from ai_observatory.storage import db, records
from ai_observatory.storage.models import Item
from ai_observatory.synthesis.llm import LLMResponse

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _item(item_id: str, published_at: datetime) -> Item:
    return Item(
        id=item_id,
        title=f"Item {item_id}",
        url=f"https://example.com/{item_id}",
        source="Test Source",
        source_priority=1,
        category="news",
        published_at=published_at,
        collected_at=published_at,
        summary="",
        raw="{}",
    )


class _StaticFetcher:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def get(self, url: str) -> bytes:
        return self._content


class TestCollectPipelineDeduplication:
    def test_two_sources_sharing_a_duplicate_item_produce_one_row_and_one_line(
        self,
    ) -> None:
        shared_feed_bytes = (FIXTURES_DIR / "feed_valid.xml").read_bytes()

        source_a = Source(
            name="Source A",
            collector="rss",
            url="https://a.example.com/feed.xml",
            category="lab",
            priority=1,
        )
        source_b = Source(
            name="Source B",
            collector="rss",
            url="https://b.example.com/feed.xml",
            category="lab",
            priority=2,
        )

        collector_a = RssCollector(
            _StaticFetcher(shared_feed_bytes), summary_max_chars=500
        )
        collector_b = RssCollector(
            _StaticFetcher(shared_feed_bytes), summary_max_chars=500
        )

        collected = collector_a.collect(source_a) + collector_b.collect(source_b)
        # Same feed bytes from both sources -> identical urls -> identical
        # persistent ids -> a genuine duplicate-item scenario across sources.
        deduped = dedup_batch(collected)

        connection = db.connect(":memory:")
        try:
            db.upsert_items(connection, deduped)

            row_count = connection.execute(
                "SELECT COUNT(*) FROM items WHERE title = 'First Item'"
            ).fetchone()[0]
            assert row_count == 1

            target_date = date(2026, 7, 20)
            day_items = db.items_for_date(connection, target_date)
            content = records.render_markdown(day_items, [], target_date, "hybrid")

            assert content.count("First Item") == 1
        finally:
            connection.close()


class TestWriteDailyRecordsWindow:
    def test_only_in_window_and_today_files_are_written(self, tmp_path: Path) -> None:
        today = date(2026, 7, 20)
        window_days = 7

        in_window = date(2026, 7, 15)
        out_of_window = date(2020, 1, 1)
        future_dated = date(2026, 7, 25)

        connection = db.connect(":memory:")
        try:
            db.upsert_items(
                connection,
                [
                    _item("in-window", datetime(2026, 7, 15, 9, tzinfo=UTC)),
                    _item("out-of-window", datetime(2020, 1, 1, 9, tzinfo=UTC)),
                    _item("future-dated", datetime(2026, 7, 25, 9, tzinfo=UTC)),
                ],
            )

            candidate_dates = {in_window, out_of_window, future_dated, today}
            records_dir = tmp_path / "records"

            _write_daily_records(
                connection, records_dir, candidate_dates, today, window_days, "hybrid"
            )

            assert (records_dir / f"{in_window.isoformat()}.md").exists()
            assert (records_dir / f"{today.isoformat()}.md").exists()
            assert not (records_dir / f"{out_of_window.isoformat()}.md").exists()
            assert not (records_dir / f"{future_dated.isoformat()}.md").exists()
        finally:
            connection.close()


class TestWriteDailyRecordsMissingVerdict:
    def test_item_without_significance_row_renders_as_set_aside(
        self, tmp_path: Path
    ) -> None:
        """A historical in-window day has items with no significance verdict
        (classification only ever runs for today). The render must still
        succeed and treat the unclassified item as set-aside (ROUTINE)."""
        today = date(2026, 7, 20)
        historical_date = date(2026, 7, 15)

        connection = db.connect(":memory:")
        try:
            db.upsert_items(
                connection,
                [_item("no-verdict", datetime(2026, 7, 15, 9, tzinfo=UTC))],
            )
            # Deliberately no db.upsert_significance call for this item.

            records_dir = tmp_path / "records"
            _write_daily_records(
                connection,
                records_dir,
                {historical_date, today},
                today,
                window_days=7,
                mode="hybrid",
            )

            content = (records_dir / f"{historical_date.isoformat()}.md").read_text(
                encoding="utf-8"
            )
            set_aside_section = content[content.index("## Set aside") :]
            significant_section = content[
                content.index("## Significant") : content.index("## Set aside")
            ]
            assert "Item no-verdict" in set_aside_section
            assert "Item no-verdict" not in significant_section
        finally:
            connection.close()


class _FakeFetcher:
    """Serves a fixed fixture regardless of the requested URL."""

    def __init__(self, *, user_agent: str) -> None:
        self.user_agent = user_agent

    def get(self, url: str) -> bytes:
        return (FIXTURES_DIR / "feed_hybrid_filter.xml").read_bytes()


class _FakeOllamaClient:
    """Fake `LLMClient`: SIGNIFICANT for any prompt not pre-filtered by rules."""

    def __init__(self, url: str, model: str, timeout: float) -> None:
        self.url = url
        self.model = model
        self.timeout = timeout
        self.calls = 0

    def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text="SIGNIFICANT", model=self.model, raw={})


class _FixedToday(datetime):
    """Freezes `datetime.now(UTC)` to match the hybrid-filter fixture's date."""

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001 - matches datetime.now signature
        return datetime(2026, 7, 20, 12, 0, tzinfo=tz)


class TestCollectEndToEnd:
    def test_collect_classifies_renders_both_buckets_and_hybrid_mode_header(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        sources_path = tmp_path / "sources.yaml"
        sources_path.write_text(
            "- name: Test Source\n"
            "  collector: rss\n"
            "  url: https://example.com/feed.xml\n"
            "  category: news\n"
            "  priority: 5\n",
            encoding="utf-8",
        )
        records_dir = tmp_path / "records"
        db_path = tmp_path / "observatory.db"

        monkeypatch.setenv("AIOBS_SOURCES_PATH", str(sources_path))
        monkeypatch.setenv("AIOBS_RECORDS_DIR", str(records_dir))
        monkeypatch.setenv("AIOBS_DB_PATH", str(db_path))
        monkeypatch.setattr("ai_observatory.cli.HttpxFetcher", _FakeFetcher)
        monkeypatch.setattr("ai_observatory.cli.OllamaClient", _FakeOllamaClient)
        monkeypatch.setattr("ai_observatory.cli.datetime", _FixedToday)

        collect()

        content = (records_dir / "2026-07-20.md").read_text(encoding="utf-8")

        assert "(filter: hybrid)" in content
        significant_section = content[
            content.index("## Significant") : content.index("## Set aside")
        ]
        set_aside_section = content[content.index("## Set aside") :]
        assert "New reasoning benchmark results announced" in significant_section
        assert "Company announces new funding round" in set_aside_section
        assert "Company announces new funding round" not in significant_section


if __name__ == "__main__":
    pytest.main([__file__])
