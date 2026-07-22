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
_DEFAULT_SUMMARY_MAX_CHARS = 500
_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.2"
_DEFAULT_OLLAMA_TIMEOUT_SECONDS = 60.0
_DEFAULT_FILTER_KEEP_PRIORITY = 1
_DEFAULT_HF_MIN_UPVOTES = 5
_DEFAULT_HN_MIN_POINTS = 30
_DEFAULT_FILTER_ROUTINE_CATEGORIES = frozenset({"research"})


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


def _optional_int_env(name: str) -> int | None:
    """Read an int env var, returning `None` on missing/invalid/negative.

    Mirrors `_int_env` but has no default: unset, blank, non-integer, or
    negative values all resolve to `None` (a disabled/opt-out signal),
    never `0` unless the env var is literally `"0"`.
    """
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _frozenset_env(name: str, default: frozenset[str]) -> frozenset[str]:
    """Read a comma-separated env var into a normalized `frozenset[str]`.

    Mirrors `_int_env`: `default` applies only when the env var is unset. A
    present value (including blank, whitespace-only, or commas-only)
    resolves to a parsed frozenset, which may be empty — an empty set
    disables the rule that consumes it. Each token is normalized with
    `.strip().casefold()`; empty tokens are dropped.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    return frozenset(
        token.strip().casefold() for token in raw.split(",") if token.strip()
    )


def _float_env(name: str, default: float) -> float:
    """Read a float env var, failing safe to `default` on missing/invalid/negative."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
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
    summary_max_chars: int
    ollama_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    filter_keep_priority: int
    hf_min_upvotes: int
    hn_min_points: int
    filter_hf_keep_upvotes: int | None
    filter_hn_keep_points: int | None
    filter_routine_categories: frozenset[str]

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
            summary_max_chars=_int_env(
                "AIOBS_SUMMARY_MAX_CHARS", _DEFAULT_SUMMARY_MAX_CHARS
            ),
            ollama_url=os.environ.get("AIOBS_OLLAMA_URL", _DEFAULT_OLLAMA_URL),
            ollama_model=os.environ.get("AIOBS_OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL),
            ollama_timeout_seconds=_float_env(
                "AIOBS_OLLAMA_TIMEOUT_SECONDS", _DEFAULT_OLLAMA_TIMEOUT_SECONDS
            ),
            filter_keep_priority=_int_env(
                "AIOBS_FILTER_KEEP_PRIORITY", _DEFAULT_FILTER_KEEP_PRIORITY
            ),
            hf_min_upvotes=_int_env("AIOBS_HF_MIN_UPVOTES", _DEFAULT_HF_MIN_UPVOTES),
            hn_min_points=_int_env("AIOBS_HN_MIN_POINTS", _DEFAULT_HN_MIN_POINTS),
            filter_hf_keep_upvotes=_optional_int_env("AIOBS_FILTER_HF_KEEP_UPVOTES"),
            filter_hn_keep_points=_optional_int_env("AIOBS_FILTER_HN_KEEP_POINTS"),
            filter_routine_categories=_frozenset_env(
                "AIOBS_FILTER_ROUTINE_CATEGORIES", _DEFAULT_FILTER_ROUTINE_CATEGORIES
            ),
        )
