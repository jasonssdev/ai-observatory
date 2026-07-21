"""Unit tests for ai_observatory.collection.sources.load_sources."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ai_observatory.collection.sources import load_sources


def _write_yaml(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadSources:
    def test_parses_yaml_into_source_objects(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            - name: OpenAI
              collector: rss
              url: https://openai.com/news/rss.xml
              category: lab
              priority: 1
            """,
        )

        sources = load_sources(path)

        assert len(sources) == 1
        assert sources[0].name == "OpenAI"
        assert sources[0].url == "https://openai.com/news/rss.xml"
        assert sources[0].category == "lab"
        assert sources[0].priority == 1

    def test_returns_all_valid_collector_types(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
            - name: RSS Source
              collector: rss
              url: https://example.com/feed.xml
              category: lab
              priority: 1
            - name: HF Source
              collector: hf_papers
              url: https://huggingface.co/api/daily_papers
              category: research
              priority: 1
            - name: HN Source
              collector: hn_algolia
              url: https://hn.algolia.com/api/v1/search_by_date
              category: community
              priority: 1
            """,
        )

        sources = load_sources(path)

        names = {source.name for source in sources}
        assert names == {"RSS Source", "HF Source", "HN Source"}

    def test_malformed_entry_is_logged_and_skipped_valid_entries_still_load(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_yaml(
            tmp_path,
            """
            - name: Good Source
              collector: rss
              url: https://example.com/feed.xml
              category: lab
              priority: 1
            - name: Bad Source
              collector: rss
              category: lab
              priority: 2
            """,
        )

        with caplog.at_level(logging.WARNING):
            sources = load_sources(path)

        assert len(sources) == 1
        assert sources[0].name == "Good Source"
        assert any(
            "Bad Source" in record.message or "Bad Source" in str(record.args)
            for record in caplog.records
        )

    def test_missing_file_raises_clear_error(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError, match="sources"):
            load_sources(missing_path)


if __name__ == "__main__":
    pytest.main([__file__])
