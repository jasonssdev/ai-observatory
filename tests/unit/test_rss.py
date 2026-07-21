"""Unit tests for ai_observatory.collection.rss: parse_feed, fetcher, collector."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from ai_observatory.collection.base import Source
from ai_observatory.collection.rss import (
    _MAX_RESPONSE_BYTES,
    HttpxFetcher,
    RssCollector,
    parse_feed,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


class TestParseFeed:
    def test_well_formed_feed_parses_entries_with_title_and_url(self) -> None:
        items = parse_feed(_fixture_bytes("feed_valid.xml"))

        assert len(items) == 2
        assert items[0].title == "First Item"
        assert items[0].url.startswith("https://example.com/articles/first-item")
        assert items[1].title == "Second Item"
        assert items[1].summary == "Summary of the second item."

    def test_malformed_feed_yields_zero_entries_without_raising(self) -> None:
        items = parse_feed(_fixture_bytes("feed_malformed.xml"))
        assert items == []

    def test_missing_published_date_defaults_to_collected_at(self) -> None:
        items = parse_feed(_fixture_bytes("feed_missing_date.xml"))

        assert len(items) == 1
        assert items[0].published_at == items[0].collected_at

    def test_non_zero_offset_pub_date_converts_to_correct_utc(self) -> None:
        items = parse_feed(_fixture_bytes("feed_offset_date.xml"))

        assert len(items) == 1
        assert items[0].published_at == datetime(2026, 7, 20, 14, 5, tzinfo=UTC)


class TestHttpxFetcher:
    def test_fetch_returns_bytes_and_sends_configured_user_agent(self) -> None:
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers["user-agent"] = request.headers["user-agent"]
            return httpx.Response(200, content=b"<rss><channel></channel></rss>")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        fetcher = HttpxFetcher(user_agent="ai-observatory-test/1.0", client=client)

        content = fetcher.get("https://example.com/feed.xml")

        assert content == b"<rss><channel></channel></rss>"
        assert captured_headers["user-agent"] == "ai-observatory-test/1.0"

    def test_fetch_rejects_response_exceeding_max_size(self) -> None:
        oversized_body = b"a" * (_MAX_RESPONSE_BYTES + 1)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=oversized_body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        fetcher = HttpxFetcher(user_agent="ai-observatory-test/1.0", client=client)

        with pytest.raises(Exception, match="size"):
            fetcher.get("https://example.com/feed.xml")


class TestRssCollectorIsolation:
    def _source(self, url: str = "https://example.com/feed.xml") -> Source:
        return Source(
            name="Test Source", collector="rss", url=url, category="lab", priority=1
        )

    def test_fetcher_failure_is_logged_and_skipped_without_raising(self) -> None:
        class RaisingFetcher:
            def get(self, url: str) -> bytes:
                raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

        collector = RssCollector(RaisingFetcher())

        result = collector.collect(self._source())

        assert result == []

    def test_successful_fetch_produces_source_attributed_items(self) -> None:
        class StaticFetcher:
            def get(self, url: str) -> bytes:
                return _fixture_bytes("feed_valid.xml")

        collector = RssCollector(StaticFetcher())
        source = self._source()

        result = collector.collect(source)

        assert len(result) == 2
        assert all(item.source == "Test Source" for item in result)
        assert all(item.source_priority == 1 for item in result)
        assert all(item.category == "lab" for item in result)


if __name__ == "__main__":
    pytest.main([__file__])
