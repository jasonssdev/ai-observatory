# Verification Report: MVP-1 Daily Record Collector

**Change**: mvp-1-daily-collector
**Mode**: Full artifacts (proposal/design/specs/tasks/apply-progress) — Strict TDD active
**Re-verify pass**: yes — re-run after a fix increment resolving the prior CRITICAL
**Verdict**: **PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 1 SUGGESTION)** — the prior CRITICAL is fully resolved; implementation is functionally solid and 100% test-green. Clear to proceed to commit/PR/archive.

## Completeness Table

| Dimension | Status |
|---|---|
| Tasks complete | 36/36 checked in `openspec/changes/mvp-1-daily-collector/tasks.md` (0 unchecked) |
| Test suite | `uv run pytest` → 42/42 passed, exit 0 (was 41; +1 new for the fix increment) |
| Lint | `uv run ruff check .` → All checks passed, exit 0 |
| Entry point | `ai-observatory --help` resolves via `ai_observatory:main` → `cli.app()`, `collect` command listed |
| sources.yaml | 9 entries present (8 P1 + Google Keyword P2), matches design |

## Build/Test Evidence (this re-verify pass, independently re-run)

```
$ uv run pytest -q
..........................................                               [100%]
42 passed in 0.06s

$ uv run ruff check .
All checks passed!
```

## CRITICAL Resolution Check

**Prior CRITICAL**: `specs/item-storage/spec.md`'s "Items Table as Source of Truth" requirement listed `canonical_url` and `title_hash` as MUST-persisted columns; the schema in `storage/db.py` omitted both, and no test covered the gap.

**Fix verified by direct source inspection** (`src/ai_observatory/storage/db.py`):
- `_SCHEMA` now declares `canonical_url TEXT NOT NULL` and `title_hash TEXT NOT NULL` (lines 16-17).
- `_INSERT_COLUMNS` is a 12-column list including both new fields, separate from the unchanged 10-column `_SELECT_COLUMNS` used for read round-trip to the `Item` model (correct — these two fields are storage-only and intentionally not added to the `Item` dataclass).
- `upsert_items` computes `canonicalize_url(item.url)` and `title_hash(item.title)` at persist time via functions imported from `ai_observatory.collection.dedup` — reusing the same identity-computation source used for `id` and in-run dedup collision resolution (no duplicated logic).

**Fix verified by test** (`tests/integration/test_db.py::TestUpsertItems::test_successful_collection_persists_canonical_url_and_title_hash`), read in full and independently re-run:
```python
row = conn.execute(
    "SELECT canonical_url, title_hash FROM items WHERE id = ?", ("a",)
).fetchone()
assert row[0] == canonicalize_url(item.url)
assert row[1] == title_hash(item.title)
```
This is a genuine behavioral assertion (not a tautology) — it round-trips through the real `upsert_items` write path and compares against the pure functions' actual output for a URL containing a tracking param (`?utm_source=x`) and a title requiring normalization (`"Hello, World!"`), so it exercises real canonicalization/hashing, not just column presence.

`test_db.py` full run (6/6, up from 5/5):
```
TestSchema::test_connect_creates_items_table_and_indexes PASSED
TestUpsertItems::test_duplicate_id_within_batch_produces_one_row PASSED
TestUpsertItems::test_rerun_with_unchanged_items_inserts_zero_new_rows PASSED
TestUpsertItems::test_raw_column_round_trips_as_valid_json PASSED
TestUpsertItems::test_successful_collection_persists_canonical_url_and_title_hash PASSED
TestItemsForDate::test_query_returns_only_matching_day_items PASSED
```

**Verdict on CRITICAL**: RESOLVED. The `items` table now persists id, title, url, canonical_url, title_hash, source, category, priority (as `source_priority`), published_at, collected_at, summary, and raw — matching `specs/item-storage/spec.md`'s "Items Table as Source of Truth" requirement in full, with a real covering test.

## Spec Scenario → Test Coverage Matrix (re-checked, all 5 domains, no regression)

### feed-collection
| Scenario | Test | Result |
|---|---|---|
| Successful fetch | `test_rss.py::TestHttpxFetcher::test_fetch_returns_bytes_and_sends_configured_user_agent` | PASS |
| Fetch failure does not raise | `test_rss.py::TestRssCollectorIsolation::test_fetcher_failure_is_logged_and_skipped_without_raising` | PASS |
| Well-formed feed parses | `test_rss.py::TestParseFeed::test_well_formed_feed_parses_entries_with_title_and_url` | PASS |
| Malformed feed yields no entries | `test_rss.py::TestParseFeed::test_malformed_feed_yields_zero_entries_without_raising` | PASS |
| One dead feed among many | `test_cli.py::test_one_of_nine_unreachable_still_exits_zero_with_record_from_rest` | PASS |
| TZ-aware → UTC / naive → UTC | Delegated to feedparser's `published_parsed`; not independently unit-tested per-branch — SUGGESTION below, unchanged | Not directly tested |
| Missing date → collected_at | `test_rss.py::TestParseFeed::test_missing_published_date_defaults_to_collected_at` | PASS |
| Request carries configured UA | `test_rss.py::TestHttpxFetcher::test_fetch_returns_bytes_and_sends_configured_user_agent` | PASS |

### item-deduplication
| Scenario | Test | Result |
|---|---|---|
| Tracking params collapse to same id | `test_dedup.py::test_tracking_param_only_diff_collapses_to_same_canonical` | PASS |
| Non-tracking params stay distinct | `test_dedup.py::test_non_tracking_param_diff_stays_distinct` | PASS |
| Cross-run persistent id stable | `test_dedup.py::test_item_id_is_deterministic_for_same_canonical_url` | PASS |
| Higher-priority source wins | `test_dedup.py::test_title_hash_collision_higher_priority_source_wins` | PASS |
| Equal priority, earlier time wins | `test_dedup.py::test_title_hash_collision_equal_priority_earlier_time_wins` | PASS |
| Equal priority+time, lexical id wins | `test_dedup.py::test_title_hash_collision_equal_priority_and_time_lexical_id_wins` | PASS |

### item-storage
| Scenario | Test | Result |
|---|---|---|
| Successful collection persists a row (id, title, url, **canonical_url**, **title_hash**, source, category, priority, published_at, collected_at, summary, raw) | `test_db.py::TestUpsertItems::test_successful_collection_persists_canonical_url_and_title_hash` | **PASS — was FAIL/CRITICAL, now resolved** |
| Duplicate id within a batch → one row | `test_db.py::TestUpsertItems::test_duplicate_id_within_batch_produces_one_row` | PASS |
| Re-run unchanged feeds → zero new rows | `test_db.py::TestUpsertItems::test_rerun_with_unchanged_items_inserts_zero_new_rows` | PASS |
| Raw column round-trips as JSON | `test_db.py::TestUpsertItems::test_raw_column_round_trips_as_valid_json` | PASS |
| Query returns only matching-day items | `test_db.py::TestItemsForDate::test_query_returns_only_matching_day_items` | PASS |

### daily-record
| Scenario | Test | Result |
|---|---|---|
| Day with items → header + count | `test_records.py::TestRenderMarkdown::test_header_states_date_and_item_count` | PASS |
| Category grouping + priority/time sort | `test_records.py::TestRenderMarkdown::test_groups_by_category_and_sorts_by_priority_then_time_desc` | PASS |
| Re-run no new items → stable, no dupes | `test_records.py::TestWriteRecord::test_full_regen_overwrites_existing_file` | PASS |
| Re-run with one new item → appears once | `test_records.py::TestWriteRecord::test_rerun_with_one_new_item_appears_once_alongside_prior` | PASS |
| Item line format | `test_records.py::TestRenderMarkdown::test_item_line_matches_expected_format` | PASS |

### collect-cli
| Scenario | Test | Result |
|---|---|---|
| Successful run produces a record | `test_cli.py::test_successful_run_exits_zero_and_writes_record` | PASS |
| Installed script resolves via main() | `test_main.py::test_main_invokes_typer_app`; confirmed live via `ai-observatory --help` | PASS |
| Defaults apply when no env vars set | `test_config.py::test_no_env_vars_uses_hardcoded_defaults` | PASS |
| Env override takes effect | `test_config.py::test_aiobs_db_path_env_var_overrides_default` | PASS |
| One unreachable source among nine | `test_cli.py::test_one_of_nine_unreachable_still_exits_zero_with_record_from_rest` | PASS |

### Mandatory Case Mapping (orchestrator-requested)
| Case | Covered by | Result |
|---|---|---|
| Success path | feed-collection, item-storage, daily-record, collect-cli (multiple) | PASS |
| Malformed feed | `test_rss.py::test_malformed_feed_yields_zero_entries_without_raising` | PASS |
| Duplicate item | `test_dedup.py::test_duplicate_id_collapses_to_one_row`, `test_db.py::test_duplicate_id_within_batch_produces_one_row`, `test_collect_integration.py` (cross-source dup) | PASS |
| Idempotent re-run | `test_db.py::test_rerun_with_unchanged_items_inserts_zero_new_rows`, `test_records.py::TestWriteRecord` (both cases) | PASS |
| Missing published_at default | `test_rss.py::test_missing_published_date_defaults_to_collected_at` | PASS |

## Re-evaluation of Prior WARNINGs and SUGGESTION

1. **WARNING — `priority` vs `source_priority` naming drift**: STILL STANDS, non-blocking. `specs/item-storage/spec.md` and `specs/item-deduplication/spec.md` refer to "priority" generically; implementation correctly uses `source_priority` throughout, matching `design.md`. Purely a documentation-clarity note for future spec readers; no functional risk. Not touched by this increment.
2. **WARNING — `main()` wiring deviation** (module-level `from ai_observatory import cli` + `cli.app()` vs. design's `from .cli import app; app()`): STILL STANDS, non-blocking. Functionally identical, exists for monkeypatch-testability, `Entry-Point Preservation` scenario genuinely satisfied by test and live invocation (`ai-observatory --help`). Not touched by this increment.
3. **SUGGESTION — TZ-aware vs. naive `published_at` normalization** not independently unit-tested per branch: STILL STANDS, non-blocking. Feedparser pre-normalizes both aware/naive formats before `_normalize_published_at` sees them, so the distinction is largely absorbed upstream; only the "missing date" branch has a dedicated test. A byte-fixture test for a non-UTC-offset date would make coverage explicit rather than inferred. Not touched by this increment.

None of the 2 WARNINGs or 1 SUGGESTION escalate to CRITICAL on re-check — all remain informational/non-blocking.

## Task Verification

All 36 original tasks remain checked `[x]` in `tasks.md`; the fix increment (schema + test for `canonical_url`/`title_hash`) is tracked in `apply-progress` as a documented follow-up increment closing the CRITICAL, not a new task-list entry — consistent with the change's completion record ("36/36 original tasks complete (all 6 phases) PLUS 1 follow-up increment").

## Design Coherence

`design.md` (engram #1320) is now fully implemented, including the item-storage schema: the maintainer's remediation choice was to implement the two spec-required columns (spec wins) rather than amend the spec to match the previously-locked design, closing the prior design/spec divergence. Architecture decisions 1 (fetch/parse seam), 2 (pure dedup + PK-based idempotent upsert, now also feeding `canonical_url`/`title_hash` at persist time), 3 (DB source of truth + full Markdown regen), and 4 (thin `main()` wrapper) are all faithfully implemented and test-covered.

## TDD Compliance (Strict TDD Module, re-checked including the fix increment)

| Check | Result | Details |
|---|---|---|
| TDD Evidence reported | Yes | Fix-increment RED/GREEN/REFACTOR row present in apply-progress (#1329), plus original 36-task evidence |
| RED confirmed for the fix | Yes | Apply-progress records the exact RED failure: `sqlite3.OperationalError: no such column: canonical_url` |
| GREEN confirmed | Yes | 42/42 pass on independent re-run just now |
| Focused test isolation | Yes | `uv run pytest tests/integration/test_db.py -q` → 6 passed, independently re-run |
| Assertion quality | Yes | New test compares against real pure-function output, not a tautology or column-existence-only check |
| No regression in prior 41 | Yes | All previously-passing tests still pass; net +1 |

**TDD Compliance**: 6/6 checks passed

## Test Layer Distribution

| Layer | Tests | Files | Tools |
|---|---|---|---|
| Unit | 30 | 5 (`test_dedup.py`, `test_rss.py`, `test_sources.py`, `test_records.py`, `test_config.py`) | pytest |
| Integration | 7 | 2 (`test_db.py` [now 6], `test_collect_integration.py` [1]) | pytest + `sqlite3.connect(":memory:")` |
| Smoke | 5 | 2 (`test_cli.py`, `test_main.py`) | Typer `CliRunner` + `httpx.MockTransport` |
| **Total** | **42** | **9** | — |

## Quality Metrics

**Linter**: No errors (`uv run ruff check .` → All checks passed)
**Type Checker**: Not configured in this project (no mypy/pyright in `pyproject.toml`) — skipped, not a failure

## Issues

### CRITICAL
None. The prior CRITICAL (item-storage `canonical_url`/`title_hash` persistence) is resolved and verified.

### WARNING
1. `priority` vs `source_priority` naming drift between spec prose and implementation column name — informational only.
2. `main()` wiring deviation from design's exact import form — informational only, functionally identical.

### SUGGESTION
1. TZ-aware vs. naive `published_at` branch coverage is implicit (via feedparser normalization) rather than explicit per-branch tests — non-blocking improvement opportunity.

## Final Verdict

**PASS WITH WARNINGS** (0 CRITICAL, 2 WARNING, 1 SUGGESTION) — the prior CRITICAL is fully resolved with real schema changes and a genuine covering test; the full 42-test suite and lint are green on independent re-run; all 5 capability domains' scenarios remain covered with no regression. The 2 WARNINGs and 1 SUGGESTION are informational/non-blocking and do not require another fix cycle.

**Clear to proceed**: commit/PR, then `sdd-archive`.
