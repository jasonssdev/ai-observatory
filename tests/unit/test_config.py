"""Unit tests for ai_observatory.config.Config."""

from __future__ import annotations

import pytest

from ai_observatory.config import Config, _float_env


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


class TestSummaryMaxChars:
    def test_unset_defaults_to_five_hundred(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_SUMMARY_MAX_CHARS", raising=False)

        config = Config.from_env()

        assert config.summary_max_chars == 500

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_SUMMARY_MAX_CHARS", "250")

        config = Config.from_env()

        assert config.summary_max_chars == 250

    def test_non_integer_value_falls_back_to_five_hundred(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_SUMMARY_MAX_CHARS", "abc")

        config = Config.from_env()

        assert config.summary_max_chars == 500

    def test_negative_value_falls_back_to_five_hundred(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_SUMMARY_MAX_CHARS", "-5")

        config = Config.from_env()

        assert config.summary_max_chars == 500

    def test_zero_is_a_valid_value(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_SUMMARY_MAX_CHARS", "0")

        config = Config.from_env()

        assert config.summary_max_chars == 0


class TestFloatEnv:
    def test_unset_returns_default(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_TEST_FLOAT", raising=False)

        assert _float_env("AIOBS_TEST_FLOAT", 60.0) == 60.0

    def test_valid_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FLOAT", "12.5")

        assert _float_env("AIOBS_TEST_FLOAT", 60.0) == 12.5

    def test_invalid_string_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FLOAT", "abc")

        assert _float_env("AIOBS_TEST_FLOAT", 60.0) == 60.0

    def test_negative_value_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FLOAT", "-1.0")

        assert _float_env("AIOBS_TEST_FLOAT", 60.0) == 60.0


class TestFilterKeepPriority:
    def test_unset_defaults_to_one(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_FILTER_KEEP_PRIORITY", raising=False)

        config = Config.from_env()

        assert config.filter_keep_priority == 1

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_KEEP_PRIORITY", "2")

        config = Config.from_env()

        assert config.filter_keep_priority == 2

    def test_invalid_value_falls_back_to_one(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_KEEP_PRIORITY", "abc")

        config = Config.from_env()

        assert config.filter_keep_priority == 1

    def test_negative_value_falls_back_to_one(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_KEEP_PRIORITY", "-1")

        config = Config.from_env()

        assert config.filter_keep_priority == 1


class TestOllamaSettings:
    def test_no_env_vars_uses_hardcoded_defaults(self, monkeypatch) -> None:
        for name in (
            "AIOBS_OLLAMA_URL",
            "AIOBS_OLLAMA_MODEL",
            "AIOBS_OLLAMA_TIMEOUT_SECONDS",
        ):
            monkeypatch.delenv(name, raising=False)

        config = Config.from_env()

        assert config.ollama_url == "http://localhost:11434"
        assert config.ollama_model == "llama3.2"
        assert config.ollama_timeout_seconds == 60.0

    def test_env_overrides_take_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_OLLAMA_URL", "http://ollama-host:9999")
        monkeypatch.setenv("AIOBS_OLLAMA_MODEL", "mistral")
        monkeypatch.setenv("AIOBS_OLLAMA_TIMEOUT_SECONDS", "30.0")

        config = Config.from_env()

        assert config.ollama_url == "http://ollama-host:9999"
        assert config.ollama_model == "mistral"
        assert config.ollama_timeout_seconds == 30.0


if __name__ == "__main__":
    pytest.main([__file__])
