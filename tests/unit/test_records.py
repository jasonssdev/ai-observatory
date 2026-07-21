"""Unit tests for ai_observatory.storage.records: render_markdown, write_record."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ai_observatory.storage.models import Item
from ai_observatory.storage.records import render_markdown, write_record


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _item(
    *,
    id_: str,
    title: str,
    category: str,
    source: str,
    source_priority: int,
    published_at: datetime,
    summary: str = "",
    url: str = "https://example.com/a",
) -> Item:
    return Item(
        id=id_,
        title=title,
        url=url,
        source=source,
        source_priority=source_priority,
        category=category,
        published_at=published_at,
        collected_at=published_at,
        summary=summary,
        raw="{}",
    )


class TestRenderMarkdown:
    def test_header_states_date_and_item_count(self) -> None:
        items = [
            _item(
                id_="a",
                title="A",
                category="lab",
                source="OpenAI",
                source_priority=1,
                published_at=_utc(2026, 7, 20, 12, 0),
            ),
            _item(
                id_="b",
                title="B",
                category="lab",
                source="OpenAI",
                source_priority=1,
                published_at=_utc(2026, 7, 20, 13, 0),
            ),
            _item(
                id_="c",
                title="C",
                category="lab",
                source="OpenAI",
                source_priority=1,
                published_at=_utc(2026, 7, 20, 14, 0),
            ),
        ]

        content = render_markdown(items, date(2026, 7, 20))

        assert content.startswith("# 2026-07-20 (3 items)")

    def test_groups_by_category_and_sorts_by_priority_then_time_desc(self) -> None:
        lab_p2_early = _item(
            id_="lab-p2",
            title="Lab P2",
            category="lab",
            source="Google",
            source_priority=2,
            published_at=_utc(2026, 7, 20, 8, 0),
        )
        lab_p1_late = _item(
            id_="lab-p1",
            title="Lab P1",
            category="lab",
            source="OpenAI",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 20, 0),
        )
        news_p1 = _item(
            id_="news-p1",
            title="News P1",
            category="news",
            source="Semianalysis",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 10, 0),
        )

        content = render_markdown(
            [lab_p2_early, news_p1, lab_p1_late], date(2026, 7, 20)
        )

        lab_index = content.index("## Lab")
        news_index = content.index("## News")
        lab_p1_index = content.index("Lab P1")
        lab_p2_index = content.index("Lab P2")

        assert lab_index < news_index
        assert lab_p1_index < lab_p2_index

    def test_item_line_matches_expected_format(self) -> None:
        item = _item(
            id_="a",
            title="Big Announcement",
            category="lab",
            source="OpenAI",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 14, 5),
            summary="A short summary.",
            url="https://openai.com/news/big-announcement",
        )

        content = render_markdown([item], date(2026, 7, 20))

        assert (
            "- [Big Announcement](https://openai.com/news/big-announcement)"
            " — OpenAI (P1) · 14:05 UTC" in content
        )
        assert "A short summary." in content


class TestWriteRecord:
    def test_full_regen_overwrites_existing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "2026-07-20.md"
        write_record(path, "# old content\n")
        write_record(path, "# new content\n")

        assert path.read_text(encoding="utf-8") == "# new content\n"

    def test_rerun_with_one_new_item_appears_once_alongside_prior(
        self, tmp_path: Path
    ) -> None:
        prior_item = _item(
            id_="prior",
            title="Prior Item",
            category="lab",
            source="OpenAI",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 9, 0),
        )
        new_item = _item(
            id_="new",
            title="New Item",
            category="lab",
            source="OpenAI",
            source_priority=1,
            published_at=_utc(2026, 7, 20, 15, 0),
        )
        path = tmp_path / "2026-07-20.md"

        write_record(path, render_markdown([prior_item], date(2026, 7, 20)))
        write_record(path, render_markdown([prior_item, new_item], date(2026, 7, 20)))

        content = path.read_text(encoding="utf-8")
        assert content.count("Prior Item") == 1
        assert content.count("New Item") == 1


if __name__ == "__main__":
    pytest.main([__file__])
