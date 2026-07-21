# Verification Report: mvp-2-hybrid-filter

**Mode**: Full artifacts (spec + design + tasks + apply-progress). Strict TDD verify module applied.
**Branch**: `feat/mvp-2-hybrid-filter` (uncommitted, matches apply-progress — no commit made yet).

## Completeness

| Check | Result |
|---|---|
| Tasks complete | 34/34 original + 2 added (2.11, 7.4) — all `[x]`, all map to real code |
| Test suite | `uv run pytest` → **131 passed**, 0 failed (baseline 96 + 35 new) |
| Lint | `uv run ruff check .` → **All checks passed** |
| Diff size | 8 modified files: 619 ins / 25 del + 3 new files (filter.py 162, test_filter.py 235, fixture 20) ≈ **1061 lines** total (apply-progress's "~1036" is a close approximation) |

## Scenario -> Test Matrix

### hybrid-filter
| Requirement / Scenario | Test | Result |
|---|---|---|
| Deterministic Auto-Keep — P1 auto-kept | `TestScoreAutoKeep.test_source_priority_at_or_below_threshold_is_significant` | PASS |
| Deterministic Drop — noise keyword (title) | `TestScoreNoiseKeywordDrop.test_title_matching_noise_keyword_is_routine` | PASS |
| Deterministic Drop — noise keyword (summary) | `TestScoreNoiseKeywordDrop.test_summary_matching_noise_keyword_is_routine` | PASS |
| LLM Verdict — significant keeps item | `TestClassifyItemsLLM.test_llm_significant_verdict_is_recorded_with_model` | PASS |
| LLM Verdict — routine sets aside | `TestClassifyItemsLLM.test_llm_routine_verdict_is_recorded` | PASS |
| Tolerant Parsing — malformed defaults ROUTINE | `TestParseVerdictMalformedDefault` (2 cases) + `TestClassifyItemsMalformedOutput` | PASS |
| Run-Level Fallback — LLM unavailable degrades whole run | `TestClassifyItemsRunLevelFallback.test_first_llm_error_degrades_whole_run` | PASS |
| Idempotent Classification — already-classified skipped | `TestUnclassifiedForDate.test_only_unclassified_items_are_returned` (mechanism-level; no direct collect()-twice E2E test) | PASS (indirect) |
| Config-Driven Thresholds — defaults/overrides | `TestFilterKeepPriority` (4 cases: unset/override/invalid/negative) | PASS |

### daily-record (delta)
| Requirement / Scenario | Test | Result |
|---|---|---|
| Markdown Generation — date/count/filter-mode header | `test_header_states_date_and_item_count`, `test_header_signals_hybrid_mode` | PASS |
| Markdown Generation — deterministic-only header | `test_header_signals_deterministic_only_mode` | PASS |
| Category Grouping / Priority Sort | `test_groups_by_category_and_sorts_by_priority_then_time_desc` | PASS |
| Two-Bucket Rendering — both populated | `TestRenderTwoBuckets.test_significant_and_set_aside_both_populated` | PASS |
| Two-Bucket Rendering — empty bucket still renders | `test_empty_set_aside_bucket_still_renders_header`, `test_empty_significant_bucket_still_renders_header` | PASS |
| Set-Aside Compact Rendering — no summary | `test_set_aside_item_renders_compact_line_without_summary` | PASS |

### item-storage (delta)
| Requirement / Scenario | Test | Result |
|---|---|---|
| Item Significance Table — idempotent creation | `test_connect_creates_item_significance_table_idempotently` | PASS |
| Idempotent Verdict Upsert | `test_upsert_same_item_id_twice_updates_in_place` | PASS |
| Query by Date | `test_query_returns_only_matching_day_verdicts` | PASS |
| Query by item id | `test_query_by_item_id_returns_its_verdict`, `test_query_by_unclassified_item_id_returns_none` | PASS |

No uncovered spec scenario found.

## Mandatory Case Coverage (per verify brief)

| Case | Verified | Evidence |
|---|---|---|
| deterministic-keep (P1) | YES | `score()` line 60-61, tested |
| deterministic-drop (noise keyword) | YES | `score()` line 63-65, tested |
| LLM-verdict-significant | YES | `classify_items` LLM branch, tested |
| LLM-verdict-routine | YES | tested |
| malformed-LLM-output -> ROUTINE | YES | `parse_verdict` default branch (line 80), tested |
| LLMError -> run-level deterministic fallback (run never fails) | YES | `classify_items` except-block flips `llm_available`, tested with `client.calls == 1` assertion proving no retry |
| idempotent re-run skips classified | YES (indirect) | `unclassified_for_date` LEFT JOIN WHERE label IS NULL, used by `cli.collect()`; no direct "call collect() twice" E2E test |
| two-bucket render | YES | `TestRenderTwoBuckets`, `TestCollectEndToEnd` |

## Central Resilience Check (filter.py:95-162)

Confirmed by source read: `llm_available` is a single run-scoped flag. On the FIRST `LLMError` (line 138), it flips to `False`, logs a warning, appends a `ROUTINE`/`DETERMINISTIC` verdict for the failing item, and `continue`s. Every subsequent UNCERTAIN item short-circuits at `if not llm_available` (line 125) straight to `ROUTINE`/`DETERMINISTIC` — **no further `llm_client.generate()` calls, no per-item retry, no abort**. The function never raises; it always returns `(verdicts, llm_available)`. Test `test_first_llm_error_degrades_whole_run` proves `client.calls == 1` across 3 uncertain items.

## Safe Default Verification (code, not claim)

- Malformed/ambiguous LLM text: `parse_verdict()` (filter.py:70-80) — only path to `SIGNIFICANT` requires substring `"significant"`; everything else falls through to `return Verdict.ROUTINE`.
- LLM unavailable: `classify_items()` except-block (filter.py:138-151) emits `Verdict.ROUTINE` explicitly — never `SIGNIFICANT` by default.
Both paths confirmed identical safe default.

## Missing-Verdict Edge Case

`cli.py::_write_daily_records` (line 58): `verdicts.get(item.id, Verdict.ROUTINE)` — an item with no `item_significance` row defaults to ROUTINE/set-aside instead of raising `KeyError`. Test `TestWriteDailyRecordsMissingVerdict.test_item_without_significance_row_renders_as_set_aside` constructs exactly this scenario (historical in-window day, no `upsert_significance` call) and asserts the item lands in `## Set aside`, not `## Significant`, and the render does not crash. Confirmed present and passing.

## item_significance Schema

```sql
CREATE TABLE IF NOT EXISTS item_significance (
    item_id TEXT PRIMARY KEY REFERENCES items(id),
    label TEXT NOT NULL, mode TEXT NOT NULL, model TEXT, classified_at TEXT NOT NULL);
```
`item_id` is both PK and FK to `items.id` (single-column combined constraint, matches design). `CREATE TABLE IF NOT EXISTS` confirmed idempotent (tested). `upsert_significance` uses `INSERT ... ON CONFLICT(item_id) DO UPDATE` (tested no-duplicate). `unclassified_for_date` and `clear_significance` both present and tested. `items` schema itself untouched (confirmed by reading `_SCHEMA`).

## Config

`filter_keep_priority: int` field, `_DEFAULT_FILTER_KEEP_PRIORITY = 1`, wired via `_int_env("AIOBS_FILTER_KEEP_PRIORITY", 1)` — fails safe to 1 on invalid/negative. 4 test cases (unset/override/invalid/negative) all pass.

## Rendering

`render_markdown` always emits both `## Significant` and `## Set aside` (with `_(none)_` placeholder when empty) — confirmed in code and tested for both empty-bucket directions. Header mode suffix `_mode_suffix()` returns `(filter: hybrid)` or `(filter: deterministic-only — LLM unavailable)` — both tested.

## Pattern Conformance

- `Significance` is a frozen `@dataclass` — confirmed.
- `LLMClient` port is injected and mocked via `_FakeLLMClient` (unit) / `_FakeOllamaClient` (integration) — no live Ollama/network anywhere in the test suite (confirmed by reading all touched test files).
- In-memory sqlite (`:memory:` / `conn` fixture) used throughout `test_db.py` and `test_collect_integration.py`.
- Storage (`storage/db.py`) imports `synthesis/filter.py` for `Mode`/`Significance`/`Verdict` — an unusual layering direction (storage -> synthesis) but explicitly locked by design.md's interfaces/data-flow section; not a freelance deviation. Noted, not flagged.

---

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD Evidence reported | YES | Full table in apply-progress, 7 rows covering all tasks |
| All tasks have tests | YES | 7/7 groups have test files |
| RED confirmed (tests exist) | YES | All listed test files/classes exist in the codebase |
| GREEN confirmed (tests pass) | YES | 131/131 pass on independent execution |
| Triangulation adequate | YES | 3-5 cases per behavior group; run-level fallback triangulated with 3-item scenario |
| Safety Net for modified files | YES | Baseline counts reported per group (18/18, 7/7, 8/8, 2/2) match pre-existing suite sizes |

**TDD Compliance**: 6/6 checks passed, with one documented deviation (below).

**Deviation**: `parse_verdict`, `build_prompt`, and `classify_items` were implemented in a single combined write rather than one function per RED/GREEN cycle (apply-progress explicitly flags this as "partial-RED"). Mitigated by 16 comprehensive test cases covering all 3 functions, all passing independently on this verify run. Classified WARNING, not CRITICAL — final coverage is real and triangulated even though the literal RED-before-code sequence wasn't followed for these 3 functions.

---

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|---|---|---|---|
| Unit | ~28 new (filter, config, records) | 3 | pytest |
| Integration | ~17 new (db in-memory sqlite, collect end-to-end w/ fakes) | 2 | pytest, sqlite3 in-memory |
| E2E | 0 | — | not installed (not applicable to this CLI tool) |
| **Total** | **131** | — | |

---

### Assertion Quality
No tautologies, no ghost loops over possibly-empty collections, no assertion-free tests found across `test_filter.py`, `test_db.py` (new classes), `test_records.py` (new classes), `test_collect_integration.py` (new classes). All assertions bind to real returned/rendered values (verdict labels, rendered markdown substrings, row counts, `client.calls` counts proving no-retry). Fakes (`_FakeLLMClient`, `_FakeOllamaClient`) are minimal (1 mock object per test, 1-4 real value assertions) — not mock-heavy.

**Assertion quality**: All assertions verify real behavior.

---

### Quality Metrics
**Linter**: No errors (`uv run ruff check .` — All checks passed)
**Type Checker**: Not configured for this project — skipped, not a failure

---

## Issues

### CRITICAL
None.

### WARNING
1. **Idempotent-classification scenario has no direct end-to-end test.** Coverage is indirect: `unclassified_for_date` (the exact query `cli.collect()` uses to select classification candidates) is unit-tested to exclude already-classified items, and `cli.py` is confirmed by source read to call it before `classify_items`. A direct "`collect()` called twice, assert LLM called 0 times / verdict unchanged on 2nd run" integration test would close this gap more strongly.
2. **Partial-RED TDD deviation** on `parse_verdict`/`build_prompt`/`classify_items` (documented above) — process deviation, not a correctness gap; final test coverage is real and passing.
3. **Review-budget overrun**: diff is ~1061 lines vs. tasks.md's forecast of 560-700 and the orchestrator's 800-line single-PR exception. Already self-flagged by apply-progress; this is a delivery-process risk for the orchestrator to accept or split, not a code-correctness issue.

### SUGGESTION
1. Add an explicit `collect()`-called-twice integration test to make idempotent-classification a first-class E2E assertion instead of an inferred one.

## Verdict: **PASS WITH WARNINGS**

All spec requirements across the three domains (hybrid-filter, daily-record, item-storage) have a passing, non-trivial covering test. The central never-fail resilience mechanism and both safe-default paths (malformed output, LLM unavailable) are confirmed correct by direct source inspection, not just by trusting the apply-progress report. The mandated missing-verdict edge case is implemented and tested correctly — no crash risk. All 34(+2) tasks are complete and match real code. Remaining findings are process/coverage-strength WARNINGs, none of which block correctness.
