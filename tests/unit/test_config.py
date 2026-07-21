"""Unit tests for ai_observatory.config.Config."""

from __future__ import annotations

import pytest

from ai_observatory.config import Config


class TestConfigDefaultsAndOverrides:
    def test_no_env_vars_uses_hardcoded_defaults(self, monkeypatch) -> None:
        for name in (
            "AIOBS_DATA_DIR",
            "AIOBS_DB_PATH",
            "AIOBS_RECORDS_DIR",
            "AIOBS_SOURCES_PATH",
            "AIOBS_USER_AGENT",
        ):
            monkeypatch.delenv(name, raising=False)

        config = Config.from_env()

        assert config.data_dir == "./data"
        assert config.db_path == "data/observatory.db"
        assert config.records_dir == "data/records"
        assert config.sources_path == "./sources.yaml"
        assert config.user_agent != ""

    def test_aiobs_db_path_env_var_overrides_default(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_DB_PATH", "/custom/path/db.sqlite3")

        config = Config.from_env()

        assert config.db_path == "/custom/path/db.sqlite3"


class TestRecordWindowDays:
    def test_unset_defaults_to_seven(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_RECORD_WINDOW_DAYS", raising=False)

        config = Config.from_env()

        assert config.record_window_days == 7

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_RECORD_WINDOW_DAYS", "3")

        config = Config.from_env()

        assert config.record_window_days == 3

    def test_zero_is_a_valid_value(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_RECORD_WINDOW_DAYS", "0")

        config = Config.from_env()

        assert config.record_window_days == 0

    def test_non_integer_value_falls_back_to_seven(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_RECORD_WINDOW_DAYS", "abc")

        config = Config.from_env()

        assert config.record_window_days == 7

    def test_negative_value_falls_back_to_seven(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_RECORD_WINDOW_DAYS", "-1")

        config = Config.from_env()

        assert config.record_window_days == 7


if __name__ == "__main__":
    pytest.main([__file__])
