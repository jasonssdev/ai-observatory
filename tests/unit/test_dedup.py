"""Unit tests for ai_observatory.collection.dedup — pure functions only."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_observatory.collection.dedup import (
    canonicalize_url,
    dedup_batch,
    item_id,
    title_hash,
)
from ai_observatory.storage.models import Item


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


_DEFAULT_PUBLISHED_AT = _utc(2026, 7, 20, 12, 0)


def _item(
    *,
    id_: str,
    title: str = "Same Story",
    url: str = "https://example.com/a",
    source: str = "Source",
    source_priority: int = 1,
    published_at: datetime = _DEFAULT_PUBLISHED_AT,
) -> Item:
    return Item(
        id=id_,
        title=title,
        url=url,
        source=source,
        source_priority=source_priority,
        category="lab",
        published_at=published_at,
        collected_at=published_at,
        summary="",
        raw="{}",
    )


class TestCanonicalizeUrl:
    def test_tracking_param_only_diff_collapses_to_same_canonical(self) -> None:
        a = canonicalize_url("https://example.com/a?utm_source=newsletter")
        b = canonicalize_url("https://example.com/a?utm_source=other")
        assert a == b

    def test_non_tracking_param_diff_stays_distinct(self) -> None:
        a = canonicalize_url("https://example.com/a?page=1")
        b = canonicalize_url("https://example.com/a?page=2")
        assert a != b

    def test_scheme_and_host_are_lowercased(self) -> None:
        assert canonicalize_url("HTTPS://Example.COM/a") == canonicalize_url(
            "https://example.com/a"
        )

    def test_default_port_is_dropped(self) -> None:
        assert canonicalize_url("https://example.com:443/a") == canonicalize_url(
            "https://example.com/a"
        )

    def test_non_default_port_is_kept(self) -> None:
        assert canonicalize_url("https://example.com:8443/a") != canonicalize_url(
            "https://example.com/a"
        )

    def test_trailing_slash_is_dropped(self) -> None:
        assert canonicalize_url("https://example.com/a/") == canonicalize_url(
            "https://example.com/a"
        )

    def test_fragment_is_dropped(self) -> None:
        assert canonicalize_url("https://example.com/a#section") == canonicalize_url(
            "https://example.com/a"
        )

    def test_kept_query_param_order_does_not_affect_canonical_url(self) -> None:
        a = canonicalize_url("https://example.com/a?x=1&y=2")
        b = canonicalize_url("https://example.com/a?y=2&x=1")
        assert a == b
        assert item_id(a) == item_id(b)


class TestTitleHashAndItemId:
    def test_title_hash_normalizes_punctuation_and_case(self) -> None:
        assert title_hash("Hello, World!") == title_hash("hello world")

    def test_title_hash_differs_for_different_titles(self) -> None:
        assert title_hash("Hello, World!") != title_hash("Goodbye, World!")

    def test_title_hash_is_deterministic(self) -> None:
        assert title_hash("Same Input") == title_hash("Same Input")

    def test_item_id_is_deterministic_for_same_canonical_url(self) -> None:
        canonical = canonicalize_url("https://example.com/a")
        assert item_id(canonical) == item_id(canonical)

    def test_item_id_differs_for_different_canonical_urls(self) -> None:
        assert item_id(canonicalize_url("https://example.com/a")) != item_id(
            canonicalize_url("https://example.com/b")
        )


class TestDedupBatch:
    def test_duplicate_id_collapses_to_one_row(self) -> None:
        items = [_item(id_="dup"), _item(id_="dup")]
        result = dedup_batch(items)
        assert len(result) == 1
        assert result[0].id == "dup"

    def test_title_hash_collision_higher_priority_source_wins(self) -> None:
        winner = _item(id_="id-p1", url="https://a.com/x", source_priority=1)
        loser = _item(id_="id-p2", url="https://b.com/y", source_priority=2)
        result = dedup_batch([loser, winner])
        assert len(result) == 1
        assert result[0].id == "id-p1"

    def test_title_hash_collision_equal_priority_earlier_time_wins(self) -> None:
        earlier = _item(
            id_="id-early",
            url="https://a.com/x",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 8, 0),
        )
        later = _item(
            id_="id-late",
            url="https://b.com/y",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 12, 0),
        )
        result = dedup_batch([later, earlier])
        assert len(result) == 1
        assert result[0].id == "id-early"

    def test_title_hash_collision_equal_priority_and_time_lexical_id_wins(
        self,
    ) -> None:
        same_time = _utc(2026, 7, 20, 8, 0)
        larger = _item(
            id_="zzz-larger",
            url="https://a.com/x",
            source_priority=1,
            published_at=same_time,
        )
        smaller = _item(
            id_="aaa-smaller",
            url="https://b.com/y",
            source_priority=1,
            published_at=same_time,
        )
        result = dedup_batch([larger, smaller])
        assert len(result) == 1
        assert result[0].id == "aaa-smaller"

    def test_distinct_stories_are_both_kept(self) -> None:
        first = _item(id_="a", title="Story A", url="https://a.com/1")
        second = _item(id_="b", title="Story B", url="https://b.com/2")
        result = dedup_batch([first, second])
        assert {item.id for item in result} == {"a", "b"}


if __name__ == "__main__":
    pytest.main([__file__])
