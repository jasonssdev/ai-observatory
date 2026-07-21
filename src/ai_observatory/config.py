"""Runtime configuration: frozen `Config` from `AIOBS_*` env vars + defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_DATA_DIR = "./data"
_DEFAULT_DB_PATH = "data/observatory.db"
_DEFAULT_RECORDS_DIR = "data/records"
_DEFAULT_SOURCES_PATH = "./sources.yaml"
_DEFAULT_USER_AGENT = (
    "ai-observatory/0.1 (+https://github.com/jasonssdev/ai-observatory)"
)
_DEFAULT_RECORD_WINDOW_DAYS = 7


def _int_env(name: str, default: int) -> int:
    """Read an int env var, failing safe to `default` on missing/invalid/negative."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


@dataclass(frozen=True)
class Config:
    data_dir: str
    db_path: str
    records_dir: str
    sources_path: str
    user_agent: str
    record_window_days: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            data_dir=os.environ.get("AIOBS_DATA_DIR", _DEFAULT_DATA_DIR),
            db_path=os.environ.get("AIOBS_DB_PATH", _DEFAULT_DB_PATH),
            records_dir=os.environ.get("AIOBS_RECORDS_DIR", _DEFAULT_RECORDS_DIR),
            sources_path=os.environ.get("AIOBS_SOURCES_PATH", _DEFAULT_SOURCES_PATH),
            user_agent=os.environ.get("AIOBS_USER_AGENT", _DEFAULT_USER_AGENT),
            record_window_days=_int_env(
                "AIOBS_RECORD_WINDOW_DAYS", _DEFAULT_RECORD_WINDOW_DAYS
            ),
        )
