"""Unit tests for ai_observatory.collection.hf_papers: parse_hf_papers, collector."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ai_observatory.collection.base import Source
from ai_observatory.collection.hf_papers import HfPapersCollector, parse_hf_papers

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES_DIR / name).read_bytes()


class TestParseHfPapers:
    def test_parse_valid_maps_fields(self) -> None:
        items = parse_hf_papers(
            _fixture_bytes("hf_daily_papers.json"), min_upvotes=5, max_chars=500
        )

        assert len(items) == 1
        item = items[0]
        assert item.title == "Scaling Reasoning with Verified Chains"
        assert item.url == "https://huggingface.co/papers/2607.12345"
        raw = json.loads(item.raw)
        assert raw["paper"]["upvotes"] == 42

    def test_parse_below_threshold_dropped(self) -> None:
        items = parse_hf_papers(
            _fixture_bytes("hf_daily_papers.json"), min_upvotes=5, max_chars=500
        )

        titles = [item.title for item in items]
        assert "Minor Ablation Study on Tokenizers" not in titles

    def test_parse_malformed_returns_empty_no_raise(self) -> None:
        items = parse_hf_papers(
            _fixture_bytes("json_malformed.json"), min_upvotes=5, max_chars=500
        )

        assert items == []

    def test_parse_empty_returns_empty(self) -> None:
        items = parse_hf_papers(b"[]", min_upvotes=5, max_chars=500)

        assert items == []


class TestHfPapersCollectorIsolation:
    def _source(self, url: str = "https://huggingface.co/api/daily_papers") -> Source:
        return Source(
            name="Hugging Face Daily Papers",
            collector="hf_papers",
            url=url,
            category="research",
            priority=1,
        )

    def test_collector_fetch_failure_isolated(self) -> None:
        class RaisingFetcher:
            def get(self, url: str) -> bytes:
                raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

        collector = HfPapersCollector(
            RaisingFetcher(), summary_max_chars=500, min_upvotes=5
        )

        result = collector.collect(self._source())

        assert result == []

    def test_successful_fetch_produces_source_attributed_items(self) -> None:
        class StaticFetcher:
            def get(self, url: str) -> bytes:
                return _fixture_bytes("hf_daily_papers.json")

        collector = HfPapersCollector(
            StaticFetcher(), summary_max_chars=500, min_upvotes=5
        )
        source = self._source()

        result = collector.collect(source)

        assert len(result) == 1
        assert all(item.source == "Hugging Face Daily Papers" for item in result)
        assert all(item.source_priority == 1 for item in result)
        assert all(item.category == "research" for item in result)


if __name__ == "__main__":
    pytest.main([__file__])
