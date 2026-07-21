"""Shared collection contracts: source config and the Fetcher/Collector seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_observatory.storage.models import Item


@dataclass(frozen=True)
class Source:
    """A single configured feed source, as loaded from ``sources.yaml``."""

    name: str
    collector: str
    url: str
    category: str
    priority: int


class Fetcher(Protocol):
    """Injectable I/O seam: retrieves raw bytes for a feed URL."""

    def get(self, url: str) -> bytes: ...


class Collector(Protocol):
    """Injectable I/O seam: collects normalized items for a single source.

    Implementations MUST NOT raise on a source's fetch/parse failure; they
    log and return an empty list instead, to isolate per-source failures.
    """

    def collect(self, source: Source) -> list[Item]: ...
