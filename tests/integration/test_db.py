"""Integration tests for ai_observatory.storage.db against :memory: sqlite."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_observatory.collection.dedup import canonicalize_url, title_hash
from ai_observatory.storage import db
from ai_observatory.storage.models import Item


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


_DEFAULT_PUBLISHED_AT = _utc(2026, 7, 20, 12, 0)


def _item(
    *,
    id_: str,
    published_at: datetime = _DEFAULT_PUBLISHED_AT,
    title: str = "Title",
    url: str = "https://example.com/a",
    raw: str = '{"key": "value"}',
) -> Item:
    return Item(
        id=id_,
        title=title,
        url=url,
        source="Source",
        source_priority=1,
        category="lab",
        published_at=published_at,
        collected_at=published_at,
        summary="Summary",
        raw=raw,
    )


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = db.connect(":memory:")
    yield connection
    connection.close()


class TestSchema:
    def test_connect_creates_items_table_and_indexes(
        self, conn: sqlite3.Connection
    ) -> None:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }

        assert "items" in tables
        assert "idx_published_at" in indexes
        assert "idx_source_priority" in indexes


class TestConnectCreatesParentDir:
    def test_connect_creates_missing_parent_dir(self, tmp_path: Path) -> None:
        db_path = tmp_path / "data" / "observatory.db"

        connection = db.connect(str(db_path))
        try:
            assert db_path.exists()
        finally:
            connection.close()


class TestUpsertItems:
    def test_duplicate_id_within_batch_produces_one_row(
        self, conn: sqlite3.Connection
    ) -> None:
        db.upsert_items(conn, [_item(id_="dup"), _item(id_="dup")])

        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert count == 1

    def test_rerun_with_unchanged_items_inserts_zero_new_rows(
        self, conn: sqlite3.Connection
    ) -> None:
        db.upsert_items(conn, [_item(id_="stable")])
        db.upsert_items(conn, [_item(id_="stable")])

        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert count == 1

    def test_raw_column_round_trips_as_valid_json(
        self, conn: sqlite3.Connection
    ) -> None:
        db.upsert_items(conn, [_item(id_="a", raw='{"title": "Original Entry"}')])

        raw_value = conn.execute(
            "SELECT raw FROM items WHERE id = ?", ("a",)
        ).fetchone()[0]
        decoded = json.loads(raw_value)
        assert decoded == {"title": "Original Entry"}

    def test_successful_collection_persists_canonical_url_and_title_hash(
        self, conn: sqlite3.Connection
    ) -> None:
        item = _item(
            id_="a",
            title="Hello, World!",
            url="https://Example.com/a/?utm_source=x",
        )

        db.upsert_items(conn, [item])

        row = conn.execute(
            "SELECT canonical_url, title_hash FROM items WHERE id = ?", ("a",)
        ).fetchone()
        assert row[0] == canonicalize_url(item.url)
        assert row[1] == title_hash(item.title)


class TestItemsForDate:
    def test_query_returns_only_matching_day_items(
        self, conn: sqlite3.Connection
    ) -> None:
        db.upsert_items(
            conn,
            [
                _item(id_="day1-a", published_at=_utc(2026, 7, 20, 1, 0)),
                _item(id_="day1-b", published_at=_utc(2026, 7, 20, 23, 0)),
                _item(id_="day2", published_at=_utc(2026, 7, 21, 1, 0)),
            ],
        )

        result = db.items_for_date(conn, date(2026, 7, 20))

        assert {item.id for item in result} == {"day1-a", "day1-b"}


if __name__ == "__main__":
    pytest.main([__file__])
