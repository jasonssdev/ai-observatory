"""End-to-end pipeline integration test: fetch -> parse -> dedup -> store -> render.

Uses two mocked sources whose feeds share one duplicate item (same canonical
URL, so same persistent id) to prove the full pipeline collapses it to a
single stored row and a single rendered Markdown line.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ai_observatory.collection.base import Source
from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.rss import RssCollector
from ai_observatory.storage import db, records

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


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


if __name__ == "__main__":
    pytest.main([__file__])
