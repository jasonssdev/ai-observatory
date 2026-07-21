"""Load configured feed sources from `sources.yaml`."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ai_observatory.collection.base import Source

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("name", "collector", "url", "category", "priority")


def load_sources(path: str | Path) -> list[Source]:
    """Load all valid sources from a YAML file, regardless of `collector` value.

    Dispatching a source's `collector` value to a matching `Collector` (or
    skipping it when no match exists) is the CLI's responsibility, not the
    loader's. A completely missing `sources.yaml` is a genuine
    misconfiguration and raises a clear, actionable `FileNotFoundError`. A
    single malformed entry (missing a required key) is logged and skipped
    so it never aborts the whole run; all other valid entries still load.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw_entries = yaml.safe_load(fh) or []
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"sources file not found at '{path}'. Create it or set "
            "AIOBS_SOURCES_PATH to a valid sources.yaml."
        ) from exc

    sources: list[Source] = []
    for entry in raw_entries:
        missing_keys = [key for key in _REQUIRED_KEYS if key not in entry]
        if missing_keys:
            logger.warning(
                "Skipping malformed source entry (missing %s): %r",
                ", ".join(missing_keys),
                entry,
            )
            continue
        sources.append(
            Source(
                name=entry["name"],
                collector=entry["collector"],
                url=entry["url"],
                category=entry["category"],
                priority=entry["priority"],
            )
        )
    return sources
