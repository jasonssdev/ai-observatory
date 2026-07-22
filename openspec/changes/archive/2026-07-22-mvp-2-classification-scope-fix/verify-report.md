# Verification Report: MVP-2 Classification Scope Fix

**Change**: mvp-2-classification-scope-fix
**Mode**: Full artifact set (spec + design + tasks + apply-progress), Strict TDD active
**Verdict**: PASS

## Completeness

| Item | Status |
|---|---|
| Tasks complete | 24/24 checked in `openspec/changes/mvp-2-classification-scope-fix/tasks.md` (verified on disk, not just apply-progress claim) |
| Spec domains covered | hybrid-filter, item-storage, collect-cli — all 3 requirements implemented |
| Design deviations | None — implementation matches design.md exactly |

## Command Evidence

| Command | Result |
|---|---|
| `uv run pytest` | **186 passed**, 0 failed (baseline was 177 → +9 new tests, matches apply-progress claim exactly) |
| `uv run ruff check .` | All checks passed |

## CRITICAL Check 1 — The bug is actually fixed and the regression test genuinely reproduces it

Confirmed in `src/ai_observatory/cli.py::collect()` (lines 114-121):
```python
today = datetime.now(UTC).date()
start = records.window_start(today, config.record_window_days)
end = today + timedelta(days=1)
...
unclassified = db.unclassified_within(connection, start, end)
```
This replaces the old `db.unclassified_for_date(connection, today)` call. `unclassified_for_date` still exists in `db.py` (kept for its own unit tests) but is no longer called from `collect()`.

**Empirically verified the regression test reproduces the old bug**: I stashed only `cli.py` (restoring the pre-fix `unclassified_for_date(today)` call while keeping the new test file, `db.py`, and `records.py` changes) and re-ran `TestCollectClassifiesWithinWindowNotOnlyToday`. Both tests in that class failed against the old code:
```
FAILED test_yesterday_dated_items_are_classified_and_render_in_correct_bucket
FAILED test_idempotent_rerun_within_window_does_not_reclassify
assert 0 > 0   (both failures)
```
This is the exact bug shape reported: yesterday-dated items receive zero verdicts under the old run-day-only scope. The working tree was fully restored afterward (`git status` confirmed only the intended 6 files modified, `git stash pop` clean, full suite re-run to 186/186 green).

Test setup: `_FixedTodayNextDay` freezes `datetime.now(UTC)` to `2026-07-21`; `feed_hybrid_filter.xml` items are dated `2026-07-20` (pubDate `Mon, 20 Jul 2026`). Default `record_window_days=7`, so 2026-07-20 is well within window. Under the old scope (`unclassified_for_date(2026-07-21)`), a `published_at LIKE '2026-07-21%'` filter excludes all fixture items entirely → 0 verdicts, matching the reported production bug.

## CRITICAL Check 2 — Window/render consistency (single source of truth)

Confirmed `records.window_start(today, window_days) -> date` is the sole definition of the window's lower bound (`records.py:20-27`), and `dates_within_window` now delegates to it (`records.py:39`: `earliest = window_start(today, window_days)`). `collect()` calls the same `records.window_start` function (`cli.py:115`) to derive the classification `start`. Both classification and render bounds are structurally guaranteed to agree — no independent recomputation exists anywhere in the codebase (verified via `rg` — no other `today - timedelta` window-lower-bound computation found).

`TestWindowStart.test_window_start_returns_today_minus_window_days` in `tests/unit/test_records.py` covers the new function directly (19/19 records tests pass). Pre-existing `dates_within_window` render/window tests pass unchanged (no test modifications to that suite were needed).

## Window Query Correctness (`unclassified_within`)

`src/ai_observatory/storage/db.py:211-231`: `published_at >= start.isoformat() AND published_at < end.isoformat()`, `LEFT JOIN item_significance ... WHERE item_significance.label IS NULL`. Mirrors `unclassified_for_date`'s column selection and `_row_to_item` hydration exactly.

`TestUnclassifiedWithin` in `tests/integration/test_db.py` (3 tests, 17/17 db tests pass):
- `test_returns_only_in_range_unclassified_items` — in-range item returned, out-of-range (2020) excluded.
- `test_excludes_classified_and_out_of_range` — already-classified item excluded via the LEFT JOIN/IS NULL condition; unclassified in-range item returned.
- `test_boundaries_start_inclusive_end_exclusive` — explicit boundary matrix: `at-start` (=start, included), `day-before-start` (excluded), `today-item` (23:59 on last in-window day, included via exclusive end = today+1), `future` (=end exactly, excluded). Assertion: `{item.id for item in result} == {"at-start", "today-item"}`. This directly proves start-inclusive/end-exclusive semantics and that "today" is never dropped.

## Idempotency Preserved

`test_idempotent_rerun_within_window_does_not_reclassify` runs `collect()` twice using a class-level call-counter fake LLM client (`_CountingOllamaClient`). First run: `total_calls > 0`. Second run: `total_calls` unchanged — proving already-classified items in the window are excluded from the second run's `unclassified_within` result (via the `label IS NULL` join condition) and never re-sent to the LLM. Also empirically confirmed this test fails against pre-fix code (see CRITICAL Check 1) since it depends on the same window-scoped query.

## Run-Level LLM Fallback Across the Window

`classify_items`'s fallback logic (first `LLMError` → deterministic-only for the whole run) is unmodified — confirmed via `git diff --stat -- src/ai_observatory/collection/` and inspection of `synthesis/filter.py` (not in the changed-files list). The fallback's own multi-item unit coverage lives in `tests/unit/test_filter.py` (pre-existing, unaffected by this change since `classify_items` only receives a list of items, agnostic to their dates). The window-widening change only affects *which* items are passed in, not the fallback mechanism itself. Integration-level confirmation: `test_deterministic_only_mode_is_reported` (`TestRunSummary`) injects `_RaisingFirstCallOllamaClient` (raises `LLMError` on first call) and asserts `"Filter mode: deterministic-only"` appears in the printed summary after a full `collect()` run against window-scoped items — proving the fallback correctly propagates through the widened scope end-to-end.

## Run Feedback

`collect()` (`cli.py`) emits, via `typer.echo`, after `_write_daily_records`: sources queried, sources returning nothing, items collected, items after dedup, items classified this run (significant/set-aside split), filter mode. `TestRunSummary.test_summary_reports_real_run_counts` asserts on `capsys.readouterr().out` (stdout, not log capture) — matches design's explicit requirement that summary assertions use capsys, not caplog. Verified counts match a real two-source run (`Sources queried: 2`, `Sources returning nothing: 1`, `Items collected: 2`, `Items after dedup: 2`, `Items classified this run: 2 (significant: 1, set aside: 1)`, `Filter mode: hybrid`).

Per-source failure visibility: `logging.basicConfig(level=logging.INFO)` added at the top of `collect()` (`cli.py:73`); `TestPerSourceFailureVisibility.test_failing_source_logs_visible_warning_and_run_completes` uses `caplog.at_level(logging.WARNING)` and asserts a warning mentioning "Failing Source" is emitted, and that `collect()` completes without raising. Confirmed `src/ai_observatory/collection/rss.py`'s never-raise/return-`[]` contract is byte-for-byte unchanged (`git diff --stat -- src/ai_observatory/collection/` produces no output — zero changes in the collectors directory).

## No Regressions

Full suite: 186/186 passed, including all pre-existing render/window/collector/dedup/storage tests unmodified in behavior. `uv run ruff check .`: clean.

## Assertion Quality Audit

Scanned all new/modified test code (`test_db.py::TestUnclassifiedWithin`, `test_records.py::TestWindowStart`, `test_collect_integration.py`'s new classes). No tautologies, no assertions-without-production-call, no ghost loops (all set-comprehension assertions compare against concrete non-empty expected sets — e.g. `{item.id for item in result} == {"at-start", "today-item"}` — never asserting inside an unguarded loop over a possibly-empty collection). No CSS/implementation-detail coupling; no excessive mocking (only the LLM client and fetcher/datetime are faked, matching the existing file's established pattern).

**Assertion quality**: All assertions verify real behavior.

## TDD Compliance

| Check | Result |
|---|---|
| TDD Evidence reported | Found in apply-progress and tasks.md |
| All tasks have tests | 24/24 |
| RED confirmed | Verified empirically for the regression test (re-ran against reverted `cli.py`, confirmed genuine `assert 0 > 0` failures) |
| GREEN confirmed | 186/186 pass on current tree |
| Triangulation | Adequate — 3 db boundary tests, 2 collect regression/idempotency tests, 2 summary tests, 1 failure-visibility test |
| Safety net for modified files | `cli.py`, `db.py`, `records.py` all had pre-existing passing test suites before modification (verified via git history / baseline 177) |

## Issues

**CRITICAL**: None.

**WARNING**: Actual changed lines (402 per `git diff --stat`, 407 per apply-progress's own count) exceed the 400-line review budget guard despite the tasks.md forecast of 180-260/Low risk. This was flagged transparently by both apply-progress and tasks.md. The overage is concentrated in `tests/integration/test_collect_integration.py` (+262) due to 5 distinct new scenarios each needing full CLI-level fixture/monkeypatch setup. Production code itself is small (63 lines across 3 files) and low-risk (no auth/security/payments/shell surface). Recommend the orchestrator apply the size/hot-path review-lens rule (likely full 4R given >400 lines) at the post-apply review gate, even though the underlying change is a narrow, well-isolated bug fix.

**SUGGESTION**: None.

## Verdict

**PASS** — the classification scope bug is genuinely fixed, the regression test empirically reproduces the pre-fix failure and passes post-fix, window/render bounds share a single source of truth (`records.window_start`), the window query is boundary-correct (start inclusive, end exclusive, excludes classified/out-of-range), idempotency and run-level LLM fallback hold across the wider scope, run feedback (summary + per-source visibility) is implemented and tested per design, and all 186 tests plus lint are green with no regressions. The only open item is the review-workload-budget overage, which is a WARNING for the orchestrator's review-lens selection, not a blocker to archive.
