"""RSS/Atom collection: fetch (I/O adapter) + parse (pure) + collect (seam)."""

from __future__ import annotations

import calendar
import dataclasses
import json
import logging
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from ai_observatory.collection.base import Source
from ai_observatory.collection.dedup import canonicalize_url, item_id
from ai_observatory.collection.text import normalize_summary
from ai_observatory.storage.models import Item

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 10.0

# Explicit per-phase timeout: connect/read/write/pool all bounded, so a
# slow-trickle feed (e.g. a server sending bytes far slower than it takes to
# fail outright) cannot stall a run unboundedly on a single scalar timeout.
_DEFAULT_TIMEOUT = httpx.Timeout(
    connect=_DEFAULT_TIMEOUT_SECONDS,
    read=_DEFAULT_TIMEOUT_SECONDS,
    write=_DEFAULT_TIMEOUT_SECONDS,
    pool=_DEFAULT_TIMEOUT_SECONDS,
)

# Feeds are small text documents; 10 MB is generous headroom while still
# preventing a misbehaving/malicious source from exhausting memory on a
# single fetch.
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _read_capped(response: httpx.Response) -> bytes:
    """Read a response body, refusing to materialize more than the cap.

    Streams the body in chunks rather than trusting `Content-Length` (which
    may be absent or wrong for chunked responses), so an oversized body is
    rejected before it is fully buffered in memory.
    """
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError(
                f"Response exceeded max allowed size of {_MAX_RESPONSE_BYTES} bytes"
            )
    return bytes(body)


class HttpxFetcher:
    """Default `Fetcher` implementation, wrapping `httpx.Client`.

    Tests inject a `client` built with `httpx.MockTransport` to avoid
    network access. `get` may raise on failure; callers (RssCollector) are
    responsible for isolating that failure.
    """

    def __init__(
        self,
        user_agent: str,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._user_agent = user_agent
        self._client = client
        self._timeout = timeout

    def get(self, url: str) -> bytes:
        headers = {"User-Agent": self._user_agent}
        if self._client is not None:
            with self._client.stream(
                "GET", url, headers=headers, follow_redirects=True
            ) as response:
                response.raise_for_status()
                return _read_capped(response)

        with (
            httpx.Client(headers=headers, timeout=self._timeout) as client,
            client.stream("GET", url, follow_redirects=True) as response,
        ):
            response.raise_for_status()
            return _read_capped(response)


def _normalize_published_at(entry: Any, default: datetime) -> datetime:
    """Normalize an entry's published date to UTC, defaulting when absent.

    feedparser already converts recognized date formats (tz-aware or naive)
    into a UTC `time.struct_time` on `published_parsed`; missing/unparseable
    dates leave that field unset, in which case we default to `collected_at`.
    """
    parsed_struct = getattr(entry, "published_parsed", None)
    if parsed_struct is None:
        return default
    try:
        return datetime.fromtimestamp(calendar.timegm(parsed_struct), tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return default


def parse_feed(data: bytes, max_chars: int) -> list[Item]:
    """Parse raw feed bytes into normalized items.

    Source-specific fields (source, source_priority, category) are left
    blank here; `RssCollector` fills them in from the `Source` config after
    fetching. Never raises: malformed bytes yield zero entries (feedparser
    itself never raises on parse errors). `summary` is normalized to plain
    text capped at `max_chars`; `raw` keeps the complete, unmodified entry.
    """
    parsed = feedparser.parse(data)
    if parsed.bozo and not parsed.entries:
        logger.warning("Feed parse produced no entries (bozo=1)")

    now = datetime.now(UTC)
    items: list[Item] = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "") or ""
        url = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or ""
        canonical = canonicalize_url(url) if url else ""
        entry_id = item_id(canonical) if canonical else item_id(title)
        raw = json.dumps(dict(entry), default=str)

        items.append(
            Item(
                id=entry_id,
                title=title,
                url=url,
                source="",
                source_priority=0,
                category="",
                published_at=_normalize_published_at(entry, now),
                collected_at=now,
                summary=normalize_summary(summary, max_chars),
                raw=raw,
            )
        )
    return items


class RssCollector:
    """Collector for a single RSS/Atom source, isolating fetch/parse failures."""

    def __init__(self, fetcher: Any, summary_max_chars: int) -> None:
        self._fetcher = fetcher
        self._summary_max_chars = summary_max_chars

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
            items = parse_feed(raw_bytes, self._summary_max_chars)
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
