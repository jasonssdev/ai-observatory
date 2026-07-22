# Tasks: MVP-2 Classification Scope Fix — ALL COMPLETE (24/24)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~180-260 (forecast) — ACTUAL: 407 (29+23+11 prod = 63; 261+68+10 test = 339) |
| 400-line budget risk | Low (forecast) — actual landed just over 400; flagged as risk in apply-progress |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

## Phase 1: Window Source of Truth (records.py) — DONE

- [x] 1.1-1.5 all complete. `window_start(today, window_days)` added; `dates_within_window` refactored to call it. `uv run pytest tests/unit/test_records.py` green (19 passed).

## Phase 2: Window-Scoped DB Query (db.py) — DONE

- [x] 2.1-2.5 all complete. `unclassified_within(connection, start_date, end_date)` added mirroring `unclassified_for_date` + `_SELECT_COLUMNS` + `_row_to_item`; start inclusive/end exclusive via ISO string comparison. `uv run pytest tests/integration/test_db.py` green (17 passed). `unclassified_for_date` kept (still referenced by its own tests).

## Phase 3: Rewire collect() (cli.py) — DONE

- [x] 3.1-3.5 all complete. Regression test (today frozen 2026-07-21, feed_hybrid_filter.xml items dated 2026-07-20 = yesterday/in-window) proves items now get verdicts (was 0 before fix). Idempotent re-run test uses a class-level call-counter fake LLM client to prove zero new LLM calls on second run. `collect()` now computes `start = records.window_start(today, config.record_window_days)`, `end = today + timedelta(days=1)`, calls `db.unclassified_within(connection, start, end)`.

## Phase 4: Run Feedback (summary + logging) — DONE

- [x] 4.1-4.6 all complete. Per-source loop tracks `sources_queried`/`empty_sources`. `logging.basicConfig(level=logging.INFO)` added at start of `collect()`. `typer.echo` summary block added after `_write_daily_records`. Also added `TestPerSourceFailureVisibility` test (not in original task list but required by collect-cli spec's "failing source produces a visible warning" scenario) — passed immediately since it exercises existing/unchanged `rss.py` fetch-failure warning behavior, confirming no spec gap.

## Phase 5: Final Gates — DONE

- [x] 5.1 `uv run pytest` — 186 passed (baseline 177 + 9 new tests).
- [x] 5.2 `uv run ruff check .` — All checks passed.
- [x] 5.3 Cross-checked all 9 original spec scenarios + 1 additional (per-source failure visibility) against written tests — no gap found.

## TDD Cycle Evidence

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|------------|
| 1.1/1.3 `window_start` | ImportError confirmed before impl | 19/19 records tests pass after adding fn | dates_within_window now delegates to window_start |
| 2.1-2.3 `unclassified_within` | 3 AttributeError failures confirmed before impl | 17/17 db tests pass after adding fn | none needed |
| 3.1 regression (yesterday-dated items) | `assert 0 > 0` failure confirmed (reproduces exact reported bug) | passes after cli.py rewire | none needed |
| 3.2 idempotent re-run | `assert 0 > 0` failure confirmed | passes after cli.py rewire | none needed |
| 4.1 summary counts | empty stdout, assertion failure confirmed | passes after typer.echo block added | none needed |
| 4.2 deterministic-only reported | empty stdout, assertion failure confirmed | passes after typer.echo block added | none needed |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command | `uv run pytest tests/unit/test_records.py tests/integration/test_db.py tests/integration/test_collect_integration.py` — all pass |
| Runtime harness | `test_collect_integration.py` regression + idempotent + summary tests exercise the real `collect()` CLI entrypoint end-to-end with fake fetcher/LLM, in-memory-equivalent tmp sqlite, no network/Ollama |
| Rollback boundary | `git revert` on branch `fix/mvp-2-classification-scope`; no migration to unwind; changes isolated to cli.py/db.py/records.py + their tests |

## Files Changed

| File | Action | Lines (+/-) |
|------|--------|------------|
| src/ai_observatory/storage/records.py | Modified | +11/-1 |
| src/ai_observatory/storage/db.py | Modified | +23/-0 |
| src/ai_observatory/cli.py | Modified | +29/-3 |
| tests/unit/test_records.py | Modified | +10/-0 |
| tests/integration/test_db.py | Modified | +68/-0 |
| tests/integration/test_collect_integration.py | Modified | +261/-1 |

## Risk Flagged

Actual changed-line total (407) exceeds the 400-line review budget guard despite the tasks.md forecast estimating 180-260 / Low risk. The overage is concentrated in tests/integration/test_collect_integration.py (261 lines) due to the number of distinct scenarios required (regression, idempotency, summary x2, failure-visibility) each needing full CLI-level fixture/monkeypatch setup matching the file's existing verbose pattern. Production code itself is small (63 lines across 3 files). Not blocked/re-scoped since decision was not required before apply per original forecast, but flagged here for `sdd-verify`/reviewer awareness.

## Status

24/24 tasks complete. All gates green (186/186 tests, ruff clean). Ready for sdd-verify.

Filesystem mirror: openspec/changes/mvp-2-classification-scope-fix/tasks.md (all checkboxes marked [x])
