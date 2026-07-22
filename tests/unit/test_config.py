"""Unit tests for ai_observatory.config.Config."""

from __future__ import annotations

import pytest

from ai_observatory.config import Config, _float_env, _frozenset_env, _optional_int_env


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


class TestHfMinUpvotes:
    def test_unset_defaults_to_five(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_HF_MIN_UPVOTES", raising=False)

        config = Config.from_env()

        assert config.hf_min_upvotes == 5

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HF_MIN_UPVOTES", "10")

        config = Config.from_env()

        assert config.hf_min_upvotes == 10

    def test_non_integer_value_falls_back_to_five(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HF_MIN_UPVOTES", "abc")

        config = Config.from_env()

        assert config.hf_min_upvotes == 5

    def test_negative_value_falls_back_to_five(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HF_MIN_UPVOTES", "-1")

        config = Config.from_env()

        assert config.hf_min_upvotes == 5


class TestHnMinPoints:
    def test_unset_defaults_to_thirty(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_HN_MIN_POINTS", raising=False)

        config = Config.from_env()

        assert config.hn_min_points == 30

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HN_MIN_POINTS", "50")

        config = Config.from_env()

        assert config.hn_min_points == 50

    def test_non_integer_value_falls_back_to_thirty(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HN_MIN_POINTS", "abc")

        config = Config.from_env()

        assert config.hn_min_points == 30

    def test_negative_value_falls_back_to_thirty(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_HN_MIN_POINTS", "-1")

        config = Config.from_env()

        assert config.hn_min_points == 30


class TestOptionalIntEnv:
    def test_unset_returns_none(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_TEST_OPTIONAL_INT", raising=False)

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") is None

    def test_blank_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_OPTIONAL_INT", "")

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") is None

    def test_valid_value_returns_int(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_OPTIONAL_INT", "42")

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") == 42

    def test_non_integer_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_OPTIONAL_INT", "abc")

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") is None

    def test_negative_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_OPTIONAL_INT", "-1")

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") is None

    def test_zero_is_a_valid_value(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_OPTIONAL_INT", "0")

        assert _optional_int_env("AIOBS_TEST_OPTIONAL_INT") == 0


class TestFilterScoreKeepThresholds:
    def test_unset_defaults_to_none(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_FILTER_HF_KEEP_UPVOTES", raising=False)
        monkeypatch.delenv("AIOBS_FILTER_HN_KEEP_POINTS", raising=False)

        config = Config.from_env()

        assert config.filter_hf_keep_upvotes is None
        assert config.filter_hn_keep_points is None

    def test_env_override_takes_effect(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_HF_KEEP_UPVOTES", "50")
        monkeypatch.setenv("AIOBS_FILTER_HN_KEEP_POINTS", "200")

        config = Config.from_env()

        assert config.filter_hf_keep_upvotes == 50
        assert config.filter_hn_keep_points == 200

    def test_invalid_value_falls_back_to_none(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_HF_KEEP_UPVOTES", "abc")
        monkeypatch.setenv("AIOBS_FILTER_HN_KEEP_POINTS", "-1")

        config = Config.from_env()

        assert config.filter_hf_keep_upvotes is None
        assert config.filter_hn_keep_points is None


class TestFrozensetEnv:
    def test_unset_returns_default(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_TEST_FROZENSET", raising=False)

        assert _frozenset_env("AIOBS_TEST_FROZENSET", frozenset({"research"})) == (
            frozenset({"research"})
        )

    def test_blank_returns_empty_frozenset(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FROZENSET", "")

        assert _frozenset_env("AIOBS_TEST_FROZENSET", frozenset({"research"})) == (
            frozenset()
        )

    def test_whitespace_only_returns_empty_frozenset(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FROZENSET", "   ")

        assert _frozenset_env("AIOBS_TEST_FROZENSET", frozenset({"research"})) == (
            frozenset()
        )

    def test_commas_only_returns_empty_frozenset(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FROZENSET", ",,,")

        assert _frozenset_env("AIOBS_TEST_FROZENSET", frozenset({"research"})) == (
            frozenset()
        )

    def test_values_are_normalized_strip_and_casefold(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FROZENSET", " Research, Lab ")

        result = _frozenset_env("AIOBS_TEST_FROZENSET", frozenset())

        assert result == frozenset({"research", "lab"})

    def test_empty_tokens_are_dropped(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_TEST_FROZENSET", "research,,lab,")

        result = _frozenset_env("AIOBS_TEST_FROZENSET", frozenset())

        assert result == frozenset({"research", "lab"})


class TestFilterRoutineCategories:
    def test_unset_defaults_to_research(self, monkeypatch) -> None:
        monkeypatch.delenv("AIOBS_FILTER_ROUTINE_CATEGORIES", raising=False)

        config = Config.from_env()

        assert config.filter_routine_categories == frozenset({"research"})

    def test_env_override_is_parsed_and_normalized(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_ROUTINE_CATEGORIES", " Research, Lab ")

        config = Config.from_env()

        assert config.filter_routine_categories == frozenset({"research", "lab"})

    def test_blank_env_var_disables_the_rule(self, monkeypatch) -> None:
        monkeypatch.setenv("AIOBS_FILTER_ROUTINE_CATEGORIES", "")

        config = Config.from_env()

        assert config.filter_routine_categories == frozenset()


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
        assert config.ollama_model == "qwen2.5:7b"
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
