"""Render and write daily Markdown records, fully regenerated from the DB."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from ai_observatory.storage.models import Item

_CATEGORY_ORDER = [
    "lab",
    "research",
    "newsletter",
    "news",
    "tooling",
    "community",
]


def window_start(today: date, window_days: int) -> date:
    """Return the earliest date included in the render/classify window.

    Single source of truth for the window's lower bound, shared by
    `dates_within_window` (render) and the CLI's classification scope, so
    the two cannot drift apart.
    """
    return today - timedelta(days=window_days)


def dates_within_window(
    candidate_dates: set[date], today: date, window_days: int
) -> set[date]:
    """Return the subset of `candidate_dates` within `window_days` of `today`.

    Keeps every date `d` where `(today - window_days) <= d <= today`.
    `today` is always included in the result, even if absent from
    `candidate_dates`. Dates after `today` (future-dated) are excluded.
    """
    earliest = window_start(today, window_days)
    kept = {d for d in candidate_dates if earliest <= d <= today}
    kept.add(today)
    return kept


def _sort_key(item: Item) -> tuple[int, float]:
    # priority ascending, published_at descending (negate timestamp).
    return (item.source_priority, -item.published_at.timestamp())


def _item_line(item: Item) -> str:
    time_label = item.published_at.strftime("%H:%M UTC")
    return (
        f"- [{item.title}]({item.url}) — {item.source} "
        f"(P{item.source_priority}) · {time_label}"
    )


def _mode_suffix(mode: str) -> str:
    if mode == "hybrid":
        return "(filter: hybrid)"
    return "(filter: deterministic-only — LLM unavailable)"


def _render_significant_section(items: list[Item]) -> list[str]:
    lines = ["## Significant", ""]
    if not items:
        lines.append("_(none)_")
        lines.append("")
        return lines

    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)

    known_categories = [c for c in _CATEGORY_ORDER if c in grouped]
    unknown_categories = sorted(c for c in grouped if c not in _CATEGORY_ORDER)
    ordered_categories = known_categories + unknown_categories

    for category in ordered_categories:
        lines.append(f"### {category.capitalize()}")
        lines.append("")
        for item in sorted(grouped[category], key=_sort_key):
            lines.append(_item_line(item))
            if item.summary:
                lines.append(f"  {item.summary}")
        lines.append("")

    return lines


def _render_set_aside_section(items: list[Item]) -> list[str]:
    lines = ["## Set aside", ""]
    if not items:
        lines.append("_(none)_")
        lines.append("")
        return lines

    for item in sorted(items, key=_sort_key):
        lines.append(_item_line(item))
    lines.append("")
    return lines


def render_markdown(
    significant: list[Item], set_aside: list[Item], target_date: date, mode: str
) -> str:
    """Render the full Markdown record for `target_date` from two buckets.

    `## Significant` keeps the existing category grouping and priority
    sort. `## Set aside` renders a compact list (no summary), not grouped
    by category. Both sections always render, even when empty (with a
    `_(none)_` placeholder). The header states the date, the combined
    item count, and the run's filter mode.
    """
    total = len(significant) + len(set_aside)
    lines = [
        f"# {target_date.isoformat()} ({total} items) {_mode_suffix(mode)}",
        "",
    ]
    lines.extend(_render_significant_section(significant))
    lines.extend(_render_set_aside_section(set_aside))

    return "\n".join(lines).rstrip() + "\n"


def write_record(path: Path, content: str) -> None:
    """Write `content` to `path`, always overwriting (never appending)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
