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


if __name__ == "__main__":
    pytest.main([__file__])
