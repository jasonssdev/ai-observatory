"""Data models shared across collection and storage layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

#: `Item.raw` key holding the normalized popularity score (int).
SIGNAL_SCORE_KEY = "signal_score"

#: `Item.raw` key holding the `SignalScale` tag for `SIGNAL_SCORE_KEY`.
SIGNAL_SCALE_KEY = "signal_scale"


class SignalScale(StrEnum):
    """Scale tag for the normalized popularity score in `Item.raw`."""

    HF_UPVOTES = "hf_upvotes"
    HN_POINTS = "hn_points"


@dataclass(frozen=True)
class Item:
    """A single normalized, source-attributed feed entry.

    ``id`` is the stable persistent identity (sha256 of the canonical URL).
    ``published_at`` and ``collected_at`` are always UTC, tz-aware.
    ``raw`` is the original source entry serialized as a JSON string. The
    HF Daily Papers and HN Algolia collectors additionally inject two
    additive, namespaced keys: ``SIGNAL_SCORE_KEY`` (int) and
    ``SIGNAL_SCALE_KEY`` (a ``SignalScale`` member), used by the
    deterministic score-keep classification rule. Other collectors (e.g.
    RSS) do not inject these keys.
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
