"""SQLite storage: schema, idempotent upsert, and date-scoped queries."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from ai_observatory.collection.dedup import canonicalize_url, title_hash
from ai_observatory.storage.models import Item

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
