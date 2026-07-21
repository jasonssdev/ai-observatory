"""Pure deduplication functions: canonical identity + in-run collision resolution.

Every function here is pure (no I/O, no globals) so it is trivially and
deterministically table-testable.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ai_observatory.storage.models import Item

_TRACKING_PARAM_NAMES = {
    "ref",
    "ref_src",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "source",
    "cmpid",
}
_DEFAULT_PORTS = {"http": 80, "https": 443}
_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in _TRACKING_PARAM_NAMES


def canonicalize_url(url: str) -> str:
    """Normalize a URL to a stable canonical form for identity purposes.

    Lowercases scheme/host, drops the fragment, default port, and trailing
    slash, and strips tracking query params while preserving all others.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()

    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None
    netloc = hostname if port is None else f"{hostname}:{port}"

    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    kept_params = sorted(
        (
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not _is_tracking_param(key)
        ),
        key=lambda pair: (pair[0], pair[1]),
    )
    query = urlencode(kept_params)

    return urlunsplit((scheme, netloc, path, query, ""))


def title_hash(title: str) -> str:
    """Hash of a title: lowercased, punctuation stripped, whitespace collapsed."""
    normalized = _PUNCTUATION_RE.sub("", title.lower())
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def item_id(canonical_url: str) -> str:
    """Stable persistent identity: sha256 of the canonical URL."""
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def _wins(candidate: Item, current: Item) -> bool:
    """True if `candidate` should replace `current` under the collision rule.

    Keep the highest-priority source (lowest priority int); ties break by
    earliest published_at, then lexically smallest id.
    """
    if candidate.source_priority != current.source_priority:
        return candidate.source_priority < current.source_priority
    if candidate.published_at != current.published_at:
        return candidate.published_at < current.published_at
    return candidate.id < current.id


def dedup_batch(items: list[Item]) -> list[Item]:
    """Deduplicate a batch of items.

    Step 1: collapse items sharing the same persistent id.
    Step 2: collapse items whose normalized-title hash collides (same story
    from different URLs), keeping the winner per `_wins`.
    """
    by_id: dict[str, Item] = {}
    for item in items:
        current = by_id.get(item.id)
        if current is None or _wins(item, current):
            by_id[item.id] = item

    by_title: dict[str, Item] = {}
    for item in by_id.values():
        key = title_hash(item.title)
        current = by_title.get(key)
        if current is None or _wins(item, current):
            by_title[key] = item

    return sorted(by_title.values(), key=lambda item: item.id)
