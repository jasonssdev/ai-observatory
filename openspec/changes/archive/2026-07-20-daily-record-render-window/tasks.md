# Tasks: Bound Daily-Record Rendering to a Recent Window

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~150-200 (config.py, storage/records.py, cli.py + 3 test files) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Config `record_window_days` + fail-safe `_int_env` | PR 1 | `uv run pytest tests/unit/test_config.py -k RecordWindow` | N/A — pure config parsing, no external I/O | Revert `config.py` + `test_config.py` hunks; no dependents yet |
| 2 | Pure `dates_within_window` helper | PR 1 | `uv run pytest tests/unit/test_records.py -k DatesWithinWindow` | N/A — pure function, no I/O | Revert `storage/records.py` addition; unused until CLI wiring |
| 3 | CLI seam `_write_daily_records` + `collect()` wiring | PR 1 | `uv run pytest tests/integration/test_collect_integration.py` | `uv run ai-observatory collect` against `data/observatory.db` | Revert `cli.py` seam extraction; restores unbounded render loop |

All three units ship in one PR (Low risk, well under the 400-line budget).

## Phase 1: Config Foundation

- [x] 1.1 RED — `tests/unit/test_config.py`: add `TestRecordWindowDays` covering: unset → `7`; `"3"` → `3`; `"0"` → `0`; `"abc"` → `7`; `"-1"` → `7` (monkeypatch `AIOBS_RECORD_WINDOW_DAYS`). Maps to spec "Config Wiring" scenarios (defaults, invalid/negative fallback).
- [x] 1.2 GREEN — `config.py`: add `_DEFAULT_RECORD_WINDOW_DAYS = 7`, module-level `_int_env(name: str, default: int) -> int` (fail-safe: missing/non-int/negative → default), `record_window_days: int` field on `Config`, wire into `from_env()` via `_int_env("AIOBS_RECORD_WINDOW_DAYS", _DEFAULT_RECORD_WINDOW_DAYS)`.
- [x] 1.3 REFACTOR — confirm `uv run ruff check config.py tests/unit/test_config.py` is clean.

## Phase 2: Pure Window Helper

- [x] 2.1 RED — `tests/unit/test_records.py`: add `TestDatesWithinWindow` (fixed `today = date(2026, 7, 20)`) covering: date inside window; boundary date `today - window_days` included; date `today - window_days - 1` excluded; `window_days == 0` → `{today}` only; `today` always included even absent from candidates; future-dated (`> today`) excluded; empty candidate set → `{today}`. Maps to spec "Full Regeneration from DB" scenarios (cold-start bounded, window-of-zero, run-date-always-rendered).
- [x] 2.2 GREEN — `storage/records.py`: implement `dates_within_window(candidate_dates: set[date], today: date, window_days: int) -> set[date]` keeping `d` where `(today - window_days) <= d <= today`, always including `today`.

## Phase 3: CLI Integration Seam

- [x] 3.1 RED — `tests/integration/test_collect_integration.py`: add deterministic test seeding an in-memory DB with items on in-window, out-of-window, and future-dated `published_at` values; call `_write_daily_records(conn, records_dir, candidate_dates, today, window_days)` directly with an injected `today` (no clock patch); assert only in-window + today `.md` files exist, out-of-window absent. Maps to spec "Cold-start backlog stays bounded" scenario.
- [x] 3.2 GREEN — `cli.py`: extract `_write_daily_records(connection, records_dir, candidate_dates, today, window_days)` seam that calls `records.dates_within_window(...)` then runs the existing `items_for_date` → `render_markdown` → `write_record` loop over the filtered set. `collect()` computes `today = datetime.now(UTC).date()` on one line (the single untestable boundary), builds `candidate_dates`, and delegates to the seam with `config.record_window_days`.
- [x] 3.3 REFACTOR — confirm existing smoke tests (`collect` exit 0, `>=1` file) stay green unchanged.

## Phase 4: Spec Alignment & Full Verification

- [x] 4.1 Cross-check implementation against `openspec/changes/daily-record-render-window/specs/daily-record/spec.md` and `specs/collect-cli/spec.md` scenarios: re-run-stable, one-new-item, cold-start-bounded, window-of-zero, run-date-always-rendered, config defaults/override/invalid-negative fallback. Pre-existing 655 out-of-window `.md` files are explicitly out of scope — no cleanup task.
- [x] 4.2 Run `uv run pytest` — full suite green.
- [x] 4.3 Run `uv run ruff check .` — clean.
