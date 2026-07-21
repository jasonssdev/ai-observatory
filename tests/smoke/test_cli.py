"""Smoke tests for the `collect` CLI command: full pipeline wiring, mocked fetcher."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import ai_observatory.cli as cli_module
from ai_observatory.cli import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
runner = CliRunner()


def _sources_yaml(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(entries), encoding="utf-8")
    return path


def _nine_source_entries() -> list[dict]:
    entries = []
    for i in range(1, 9):
        entries.append(
            {
                "name": f"Source {i}",
                "collector": "rss",
                "url": f"https://example.com/feed-{i}.xml",
                "category": "lab",
                "priority": 1,
            }
        )
    entries.append(
        {
            "name": "Dead Source",
            "collector": "rss",
            "url": "https://example.com/dead-feed.xml",
            "category": "lab",
            "priority": 1,
        }
    )
    return entries


class _FakeFetcherHealthy:
    """Fake Fetcher: 8 sources succeed, one ("dead-feed") always fails."""

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent

    def get(self, url: str) -> bytes:
        if "dead-feed" in url:
            raise RuntimeError("simulated unreachable source")
        return (FIXTURES_DIR / "feed_valid.xml").read_bytes()


class TestCollectCommand:
    def test_successful_run_exits_zero_and_writes_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sources_path = _sources_yaml(
            tmp_path,
            [
                {
                    "name": "Only Source",
                    "collector": "rss",
                    "url": "https://example.com/feed.xml",
                    "category": "lab",
                    "priority": 1,
                }
            ],
        )
        records_dir = tmp_path / "records"
        monkeypatch.setenv("AIOBS_SOURCES_PATH", str(sources_path))
        monkeypatch.setenv("AIOBS_DB_PATH", str(tmp_path / "db.sqlite3"))
        monkeypatch.setenv("AIOBS_RECORDS_DIR", str(records_dir))
        monkeypatch.setattr(cli_module, "HttpxFetcher", _FakeFetcherHealthy)

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        written_files = list(records_dir.glob("*.md"))
        assert len(written_files) >= 1

    def test_one_of_nine_unreachable_still_exits_zero_with_record_from_rest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sources_path = _sources_yaml(tmp_path, _nine_source_entries())
        records_dir = tmp_path / "records"
        monkeypatch.setenv("AIOBS_SOURCES_PATH", str(sources_path))
        monkeypatch.setenv("AIOBS_DB_PATH", str(tmp_path / "db.sqlite3"))
        monkeypatch.setenv("AIOBS_RECORDS_DIR", str(records_dir))
        monkeypatch.setattr(cli_module, "HttpxFetcher", _FakeFetcherHealthy)

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        written_files = list(records_dir.glob("*.md"))
        assert len(written_files) >= 1
        combined_content = "\n".join(
            path.read_text(encoding="utf-8") for path in written_files
        )
        assert "First Item" in combined_content


if __name__ == "__main__":
    pytest.main([__file__])
