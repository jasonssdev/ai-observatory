"""Hacker News Algolia collection: parse (pure) + collect (seam).

The HN Algolia search API returns `{"hits": [...]}`; each hit's canonical
URL is its external `url` when present, falling back to the discussion
permalink when `url` is null. Mirrors `rss.py`'s split: a pure
`parse_hn_algolia` and a thin, never-raise `HnAlgoliaCollector`.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import UTC, datetime
from typing import Any

from ai_observatory.collection.base import Source
from ai_observatory.collection.dedup import canonicalize_url, item_id
from ai_observatory.collection.text import normalize_summary
from ai_observatory.storage.models import Item

logger = logging.getLogger(__name__)

_PERMALINK_TEMPLATE = "https://news.ycombinator.com/item?id={object_id}"


def _normalize_published_at(raw_value: Any, default: datetime) -> datetime:
    if not isinstance(raw_value, str):
        return default
    try:
        normalized = raw_value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return default
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_hn_algolia(data: bytes, min_points: int, max_chars: int) -> list[Item]:
    """Parse raw HN Algolia JSON bytes into normalized items.

    Source-specific fields (source, source_priority, category) are left
    blank here; `HnAlgoliaCollector` fills them in from the `Source` config
    after fetching. Never raises: malformed/unexpected-shape JSON yields
    zero entries, logged as a warning. Hits with `points` below
    `min_points` are dropped before returning. Canonical `url` is the
    hit's external `url` when present, else the discussion permalink; the
    permalink is always retained in `raw` via `objectID`.
    """
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("HN Algolia JSON could not be decoded", exc_info=True)
        return []

    if not isinstance(payload, dict):
        logger.warning("HN Algolia JSON was not an object: %r", type(payload))
        return []

    hits = payload.get("hits")
    if not isinstance(hits, list):
        logger.warning("HN Algolia JSON missing a 'hits' list")
        return []

    now = datetime.now(UTC)
    items: list[Item] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        object_id = hit.get("objectID")
        points = hit.get("points")
        if not isinstance(object_id, str) or not isinstance(points, int):
            continue
        if points < min_points:
            continue

        title = hit.get("title") or ""
        external_url = hit.get("url")
        url = (
            external_url
            if isinstance(external_url, str) and external_url
            else _PERMALINK_TEMPLATE.format(object_id=object_id)
        )
        canonical = canonicalize_url(url)
        raw = json.dumps(hit, default=str)

        items.append(
            Item(
                id=item_id(canonical),
                title=title,
                url=url,
                source="",
                source_priority=0,
                category="",
                published_at=_normalize_published_at(hit.get("created_at"), now),
                collected_at=now,
                # HN Algolia hits carry no body/description text; summary
                # stays empty (matches other source-less-text collectors).
                summary=normalize_summary("", max_chars),
                raw=raw,
            )
        )
    return items


class HnAlgoliaCollector:
    """Collector for the HN Algolia source, isolating fetch/parse failures."""

    def __init__(self, fetcher: Any, summary_max_chars: int, min_points: int) -> None:
        self._fetcher = fetcher
        self._summary_max_chars = summary_max_chars
        self._min_points = min_points

    def collect(self, source: Source) -> list[Item]:
        try:
            raw_bytes = self._fetcher.get(source.url)
        except Exception:
            logger.warning(
                "Failed to fetch source %s (%s)",
                source.name,
                source.url,
                exc_info=True,
            )
            return []

        try:
            items = parse_hn_algolia(
                raw_bytes, self._min_points, self._summary_max_chars
            )
        except Exception:
            logger.warning(
                "Failed to parse source %s (%s)",
                source.name,
                source.url,
                exc_info=True,
            )
            return []

        return [
            dataclasses.replace(
                item,
                source=source.name,
                source_priority=source.priority,
                category=source.category,
            )
            for item in items
        ]
