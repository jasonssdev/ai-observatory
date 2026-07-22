"""Smoke tests for the `collect` CLI command: full pipeline wiring, mocked fetcher."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import ai_observatory.cli as cli_module
from ai_observatory.cli import app
from ai_observatory.synthesis.llm import LLMResponse

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


class _CapturingOllamaClient:
    """Fake `LLMClient`: captures the constructor's `model` on the class.

    Class-level (not instance-level) so the test can read it after
    `runner.invoke` returns without needing a reference to the instance
    `collect()` built internally.
    """

    captured_model: str | None = None

    def __init__(self, url: str, model: str, timeout: float) -> None:
        self.url = url
        self.model = model
        self.timeout = timeout
        type(self).captured_model = model

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text="SIGNIFICANT", model=self.model, raw={})


class TestCollectModelFlag:
    def _empty_sources_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sources_path = _sources_yaml(tmp_path, [])
        monkeypatch.setenv("AIOBS_SOURCES_PATH", str(sources_path))
        monkeypatch.setenv("AIOBS_DB_PATH", str(tmp_path / "db.sqlite3"))
        monkeypatch.setenv("AIOBS_RECORDS_DIR", str(tmp_path / "records"))
        monkeypatch.setattr(cli_module, "OllamaClient", _CapturingOllamaClient)
        _CapturingOllamaClient.captured_model = None

    def test_flag_overrides_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._empty_sources_env(tmp_path, monkeypatch)

        result = runner.invoke(app, ["collect", "--model", "qwen2.5:3b"])

        assert result.exit_code == 0
        assert _CapturingOllamaClient.captured_model == "qwen2.5:3b"

    def test_env_used_when_no_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._empty_sources_env(tmp_path, monkeypatch)
        monkeypatch.setenv("AIOBS_OLLAMA_MODEL", "mistral")

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        assert _CapturingOllamaClient.captured_model == "mistral"

    def test_config_default_used_when_neither_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._empty_sources_env(tmp_path, monkeypatch)
        monkeypatch.delenv("AIOBS_OLLAMA_MODEL", raising=False)

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        assert _CapturingOllamaClient.captured_model == "qwen2.5:7b"

    def test_flag_takes_precedence_over_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._empty_sources_env(tmp_path, monkeypatch)
        monkeypatch.setenv("AIOBS_OLLAMA_MODEL", "mistral")

        result = runner.invoke(app, ["collect", "--model", "qwen2.5:3b"])

        assert result.exit_code == 0
        assert _CapturingOllamaClient.captured_model == "qwen2.5:3b"

    def test_empty_flag_falls_back_to_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._empty_sources_env(tmp_path, monkeypatch)
        monkeypatch.delenv("AIOBS_OLLAMA_MODEL", raising=False)

        result = runner.invoke(app, ["collect", "--model", ""])

        assert result.exit_code == 0
        assert _CapturingOllamaClient.captured_model == "qwen2.5:7b"


if __name__ == "__main__":
    pytest.main([__file__])
