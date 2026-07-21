"""Data models shared across collection and storage layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Item:
    """A single normalized, source-attributed feed entry.

    ``id`` is the stable persistent identity (sha256 of the canonical URL).
    ``published_at`` and ``collected_at`` are always UTC, tz-aware.
    ``raw`` is the original source entry serialized as a JSON string.
    """

    id: str
    title: str
    url: str
    source: str
    source_priority: int
    category: str
    published_at: datetime
    collected_at: datetime
    summary: str
    raw: str
