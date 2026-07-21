"""Hugging Face Daily Papers collection: parse (pure) + collect (seam).

The HF Daily Papers API returns a JSON array of paper entries, each nesting
its community score under `paper.upvotes`. Mirrors `rss.py`'s split: a pure
`parse_hf_papers` and a thin, never-raise `HfPapersCollector`.
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

_CANONICAL_URL_TEMPLATE = "https://huggingface.co/papers/{paper_id}"


def _normalize_published_at(raw_value: Any, default: datetime) -> datetime:
    if not isinstance(raw_value, str):
        return default
    try:
        # HF timestamps are ISO-8601 with a trailing "Z"; datetime.fromisoformat
        # only accepts "+00:00" for the UTC offset prior to normalizing here.
        normalized = raw_value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return default
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_hf_papers(data: bytes, min_upvotes: int, max_chars: int) -> list[Item]:
    """Parse raw HF Daily Papers JSON bytes into normalized items.

    Source-specific fields (source, source_priority, category) are left
    blank here; `HfPapersCollector` fills them in from the `Source` config
    after fetching. Never raises: malformed/unexpected-shape JSON yields
    zero entries, logged as a warning. Papers with `paper.upvotes` below
    `min_upvotes` are dropped before returning.
    """
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("HF Daily Papers JSON could not be decoded", exc_info=True)
        return []

    if not isinstance(payload, list):
        logger.warning("HF Daily Papers JSON was not a list: %r", type(payload))
        return []

    now = datetime.now(UTC)
    items: list[Item] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        paper = entry.get("paper")
        if not isinstance(paper, dict):
            continue
        paper_id = paper.get("id")
        upvotes = paper.get("upvotes")
        if not isinstance(paper_id, str) or not isinstance(upvotes, int):
            continue
        if upvotes < min_upvotes:
            continue

        title = entry.get("title") or ""
        summary = entry.get("summary") or ""
        url = _CANONICAL_URL_TEMPLATE.format(paper_id=paper_id)
        canonical = canonicalize_url(url)
        raw = json.dumps(entry, default=str)

        items.append(
            Item(
                id=item_id(canonical),
                title=title,
                url=url,
                source="",
                source_priority=0,
                category="",
                published_at=_normalize_published_at(entry.get("publishedAt"), now),
                collected_at=now,
                summary=normalize_summary(summary, max_chars),
                raw=raw,
            )
        )
    return items


class HfPapersCollector:
    """Collector for the HF Daily Papers source, isolating fetch/parse failures."""

    def __init__(self, fetcher: Any, summary_max_chars: int, min_upvotes: int) -> None:
        self._fetcher = fetcher
        self._summary_max_chars = summary_max_chars
        self._min_upvotes = min_upvotes

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
            items = parse_hf_papers(
                raw_bytes, self._min_upvotes, self._summary_max_chars
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
