"""SQLite storage: schema, idempotent upsert, and date-scoped queries."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from ai_observatory.collection.dedup import canonicalize_url, title_hash
from ai_observatory.storage.models import Item
from ai_observatory.synthesis.filter import Mode, Significance, Verdict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    source_priority INTEGER NOT NULL,
    category TEXT NOT NULL,
    published_at TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_published_at ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_source_priority ON items(source_priority);
CREATE TABLE IF NOT EXISTS item_significance (
    item_id TEXT PRIMARY KEY REFERENCES items(id),
    label TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT,
    classified_at TEXT NOT NULL
);
"""

_SELECT_COLUMNS = (
    "id, title, url, source, source_priority, category, "
    "published_at, collected_at, summary, raw"
)

_INSERT_COLUMNS = (
    "id, title, url, canonical_url, title_hash, source, source_priority, "
    "category, published_at, collected_at, summary, raw"
)


def connect(path: str) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists (idempotent)."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(_SCHEMA)
    connection.commit()
    return connection


def upsert_items(connection: sqlite3.Connection, items: list[Item]) -> None:
    """Insert items, ignoring any whose id already exists (idempotent write)."""
    rows = [
        (
            item.id,
            item.title,
            item.url,
            canonicalize_url(item.url),
            title_hash(item.title),
            item.source,
            item.source_priority,
            item.category,
            item.published_at.isoformat(),
            item.collected_at.isoformat(),
            item.summary,
            item.raw,
        )
        for item in items
    ]
    connection.executemany(
        f"""
        INSERT OR IGNORE INTO items ({_INSERT_COLUMNS})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()


def _row_to_item(row: tuple) -> Item:
    (
        id_,
        title,
        url,
        source,
        source_priority,
        category,
        published_at,
        collected_at,
        summary,
        raw,
    ) = row
    return Item(
        id=id_,
        title=title,
        url=url,
        source=source,
        source_priority=source_priority,
        category=category,
        published_at=datetime.fromisoformat(published_at),
        collected_at=datetime.fromisoformat(collected_at),
        summary=summary,
        raw=raw,
    )


def items_for_date(connection: sqlite3.Connection, target_date: date) -> list[Item]:
    """Return all items whose published_at falls on `target_date` (UTC)."""
    pattern = f"{target_date.isoformat()}%"
    cursor = connection.execute(
        f"SELECT {_SELECT_COLUMNS} FROM items WHERE published_at LIKE ? "
        "ORDER BY published_at",
        (pattern,),
    )
    return [_row_to_item(row) for row in cursor.fetchall()]


def upsert_significance(
    connection: sqlite3.Connection, verdicts: list[Significance]
) -> None:
    """Insert or update significance verdicts, keyed on item id (idempotent).

    Re-writing a verdict for an already-classified item updates the
    existing row (label/mode/model/classified_at) rather than creating a
    duplicate.
    """
    classified_at = datetime.now(UTC).isoformat()
    rows = [
        (verdict.item_id, verdict.label, verdict.mode, verdict.model, classified_at)
        for verdict in verdicts
    ]
    connection.executemany(
        """
        INSERT INTO item_significance (item_id, label, mode, model, classified_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            label = excluded.label,
            mode = excluded.mode,
            model = excluded.model,
            classified_at = excluded.classified_at
        """,
        rows,
    )
    connection.commit()


def significance_for_date(
    connection: sqlite3.Connection, target_date: date
) -> list[Significance]:
    """Return persisted verdicts for items published on `target_date` (UTC)."""
    pattern = f"{target_date.isoformat()}%"
    cursor = connection.execute(
        """
        SELECT s.item_id, s.label, s.mode, s.model
        FROM item_significance s
        JOIN items i ON i.id = s.item_id
        WHERE i.published_at LIKE ?
        """,
        (pattern,),
    )
    return [
        Significance(
            item_id=row[0], label=Verdict(row[1]), mode=Mode(row[2]), model=row[3]
        )
        for row in cursor.fetchall()
    ]


def significance_for_item(
    connection: sqlite3.Connection, item_id: str
) -> Significance | None:
    """Return the persisted verdict for a single item id, or `None`."""
    row = connection.execute(
        "SELECT item_id, label, mode, model FROM item_significance WHERE item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return Significance(
        item_id=row[0], label=Verdict(row[1]), mode=Mode(row[2]), model=row[3]
    )


def unclassified_for_date(
    connection: sqlite3.Connection, target_date: date
) -> list[Item]:
    """Return items published on `target_date` (UTC) with no verdict yet."""
    pattern = f"{target_date.isoformat()}%"
    cursor = connection.execute(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM items
        LEFT JOIN item_significance ON item_significance.item_id = items.id
        WHERE items.published_at LIKE ? AND item_significance.label IS NULL
        ORDER BY items.published_at
        """,
        (pattern,),
    )
    return [_row_to_item(row) for row in cursor.fetchall()]


def clear_significance(connection: sqlite3.Connection) -> None:
    """Delete all persisted significance verdicts (reclassify path)."""
    connection.execute("DELETE FROM item_significance")
    connection.commit()
