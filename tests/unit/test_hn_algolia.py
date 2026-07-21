"""Unit tests for ai_observatory.collection.hn_algolia: parse_hn_algolia, collector."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ai_observatory.collection.base import Source
from ai_observatory.collection.hn_algolia import HnAlgoliaCollector, parse_hn_algolia

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


class TestParseHnAlgolia:
    def test_parse_valid_external_url(self) -> None:
        items = parse_hn_algolia(
            _fixture_bytes("hn_algolia.json"), min_points=30, max_chars=500
        )

        matching = [
            item for item in items if item.title == "New open-weight model released"
        ]
        assert len(matching) == 1
        assert matching[0].url == "https://example.com/new-model-release"

    def test_parse_null_url_falls_back_to_permalink(self) -> None:
        items = parse_hn_algolia(
            _fixture_bytes("hn_algolia.json"), min_points=30, max_chars=500
        )

        matching = [
            item
            for item in items
            if item.title == "Ask HN: How do you evaluate LLM agents?"
        ]
        assert len(matching) == 1
        item = matching[0]
        assert item.url == "https://news.ycombinator.com/item?id=222222"
        raw = json.loads(item.raw)
        assert raw["objectID"] == "222222"

    def test_parse_below_threshold_dropped(self) -> None:
        items = parse_hn_algolia(
            _fixture_bytes("hn_algolia.json"), min_points=30, max_chars=500
        )

        titles = [item.title for item in items]
        assert "Minor tooling update discussion" not in titles

    def test_parse_malformed_returns_empty_no_raise(self) -> None:
        items = parse_hn_algolia(
            _fixture_bytes("json_malformed.json"), min_points=30, max_chars=500
        )

        assert items == []

    def test_parse_empty_returns_empty(self) -> None:
        items = parse_hn_algolia(b'{"hits": []}', min_points=30, max_chars=500)

        assert items == []


class TestHnAlgoliaCollectorIsolation:
    def _source(
        self, url: str = "https://hn.algolia.com/api/v1/search_by_date"
    ) -> Source:
        return Source(
            name="Hacker News (AI)",
            collector="hn_algolia",
            url=url,
            category="community",
            priority=1,
        )

    def test_collector_fetch_failure_isolated(self) -> None:
        class RaisingFetcher:
            def get(self, url: str) -> bytes:
                raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

        collector = HnAlgoliaCollector(
            RaisingFetcher(), summary_max_chars=500, min_points=30
        )

        result = collector.collect(self._source())

        assert result == []

    def test_successful_fetch_produces_source_attributed_items(self) -> None:
        class StaticFetcher:
            def get(self, url: str) -> bytes:
                return _fixture_bytes("hn_algolia.json")

        collector = HnAlgoliaCollector(
            StaticFetcher(), summary_max_chars=500, min_points=30
        )
        source = self._source()

        result = collector.collect(source)

        assert len(result) == 2
        assert all(item.source == "Hacker News (AI)" for item in result)
        assert all(item.source_priority == 1 for item in result)
        assert all(item.category == "community" for item in result)


if __name__ == "__main__":
    pytest.main([__file__])
