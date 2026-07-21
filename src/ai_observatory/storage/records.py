"""Render and write daily Markdown records, fully regenerated from the DB."""

from __future__ import annotations

from datetime import date
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


def _sort_key(item: Item) -> tuple[int, float]:
    # priority ascending, published_at descending (negate timestamp).
    return (item.source_priority, -item.published_at.timestamp())


def render_markdown(items: list[Item], target_date: date) -> str:
    """Render the full Markdown record for `target_date` from `items`.

    Groups by category (fixed order, then any unknown categories sorted
    lexically), and within each group sorts by source priority ascending
    then published_at descending.
    """
    lines = [f"# {target_date.isoformat()} ({len(items)} items)", ""]

    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)

    known_categories = [c for c in _CATEGORY_ORDER if c in grouped]
    unknown_categories = sorted(c for c in grouped if c not in _CATEGORY_ORDER)
    ordered_categories = known_categories + unknown_categories

    for category in ordered_categories:
        lines.append(f"## {category.capitalize()}")
        lines.append("")
        for item in sorted(grouped[category], key=_sort_key):
            time_label = item.published_at.strftime("%H:%M UTC")
            line = (
                f"- [{item.title}]({item.url}) — {item.source} "
                f"(P{item.source_priority}) · {time_label}"
            )
            lines.append(line)
            if item.summary:
                lines.append(f"  {item.summary}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_record(path: Path, content: str) -> None:
    """Write `content` to `path`, always overwriting (never appending)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
