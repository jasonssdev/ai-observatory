"""End-to-end pipeline integration test: fetch -> parse -> dedup -> store -> render.

Uses two mocked sources whose feeds share one duplicate item (same canonical
URL, so same persistent id) to prove the full pipeline collapses it to a
single stored row and a single rendered Markdown line.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_observatory.cli import _write_daily_records
from ai_observatory.collection.base import Source
from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.rss import RssCollector
from ai_observatory.storage import db, records
from ai_observatory.storage.models import Item

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

        collector_a = RssCollector(_StaticFetcher(shared_feed_bytes))
        collector_b = RssCollector(_StaticFetcher(shared_feed_bytes))

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
            content = records.render_markdown(day_items, target_date)

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
                connection, records_dir, candidate_dates, today, window_days
            )

            assert (records_dir / f"{in_window.isoformat()}.md").exists()
            assert (records_dir / f"{today.isoformat()}.md").exists()
            assert not (records_dir / f"{out_of_window.isoformat()}.md").exists()
            assert not (records_dir / f"{future_dated.isoformat()}.md").exists()
        finally:
            connection.close()


if __name__ == "__main__":
    pytest.main([__file__])
