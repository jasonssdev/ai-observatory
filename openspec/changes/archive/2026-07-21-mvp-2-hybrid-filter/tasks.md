# Tasks: MVP-2 Hybrid Daily Filter

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~560-700 (config.py +10, test_config.py +25, storage/db.py +70, test_db.py +90, synthesis/filter.py NEW +130, test_filter.py NEW +170, storage/records.py +50, test_records.py +70, cli.py +25, test_collect_integration.py +20) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: filter + config + tests -> PR 2: db + records + cli + tests |
| Delivery strategy | auto-forecast (not a listed enum; treated as auto-chain-equivalent — proceed with first slice, confirm chain strategy) |
| Chain strategy | feature-branch-chain (PR 2 needs `Verdict`/`Significance`/`classify_items` from PR 1) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|------------------|--------------------|
| 1 | Deterministic filter core: `config.py` (`filter_keep_priority`) + `synthesis/filter.py` (`Verdict`, `Mode`, `Significance`, `score`, `parse_verdict`, `build_prompt`, `classify_items`) | PR 1 (base: tracker/main) | `uv run pytest tests/unit/test_config.py tests/unit/test_filter.py -q` | N/A — pure functions + fake `LLMClient`, zero network, zero DB | Revert `config.py` `filter_keep_priority` diff + delete `synthesis/filter.py` + `test_filter.py`; nothing else references `filter.py` yet |
| 2 | Persistence + rendering + CLI wiring: `storage/db.py` (`item_significance` + helpers), `storage/records.py` (two-bucket render), `cli.py` (classify step) | PR 2 (base: PR 1 branch) | `uv run pytest tests/integration/test_db.py tests/unit/test_records.py tests/integration/test_collect_integration.py -q` | `uv run ai-observatory collect` against a temp `sources.yaml` + `:memory:`/tmp DB with a fake `LLMClient` injected in the integration test (no live Ollama) | Revert `storage/db.py` schema/helpers, `storage/records.py` signature, `cli.py` wiring, and the 3 test files; PR 1's pure `filter.py` stays intact and unused |

## Execution note (deviation from listed phase order)

Phase 3's pure types (`Verdict`, `Mode`, `Significance`) were implemented
**before** Phase 2's storage helpers, not after, because `storage/db.py`'s
`upsert_significance`/`significance_for_date` helpers take/return
`Significance` objects (per design's data-flow: `classify_items` ->
`db.upsert_significance`) and therefore need the type to exist first. Actual
build order: 3.1-3.2 (types + `score()`) -> Phase 1 (config) -> Phase 2
(storage) -> Phase 3.3-3.6 (noise/uncertain branches) -> Phase 4 (parser/prompt)
-> Phase 5 (`classify_items`) -> Phase 6 (rendering) -> Phase 7 (CLI). All
listed tasks below are complete regardless of build order.

Also added one helper beyond this task list: `db.significance_for_item(connection, item_id)`,
required by `specs/item-storage/spec.md`'s "Query by item id returns its verdict"
scenario, which this tasks.md omitted from the Phase 2 helper list. RED/GREEN
cycle followed (`tests/integration/test_db.py::TestSignificanceForItem`).

## Phase 1: Config (`config.py`) — Req: Configuration-Driven Thresholds

- [x] 1.1 RED `test_config.py::test_filter_keep_priority` — unset -> `1`; `AIOBS_FILTER_KEEP_PRIORITY=2` -> `2`; invalid/negative -> `1`
- [x] 1.2 GREEN add `_DEFAULT_FILTER_KEEP_PRIORITY = 1`, `filter_keep_priority: int` field, `from_env` wiring via `_int_env("AIOBS_FILTER_KEEP_PRIORITY", 1)`

## Phase 2: Storage — `item_significance` (`storage/db.py`) — Req: Item Significance Table / Idempotent Upsert / Query by Date

- [x] 2.1 RED `test_db.py::test_item_significance_table_idempotent` — `connect()` twice on same file, exactly one table
- [x] 2.2 GREEN add `item_significance` to `_SCHEMA` via `CREATE TABLE IF NOT EXISTS` (`item_id TEXT PRIMARY KEY REFERENCES items(id)`, `label`, `mode`, `model`, `classified_at`); `items` schema untouched
- [x] 2.3 RED `test_db.py::test_upsert_significance_idempotent` — upsert same `item_id` twice with different labels -> 1 row, latest values
- [x] 2.4 GREEN `upsert_significance(connection, rows)` — `INSERT ... ON CONFLICT(item_id) DO UPDATE`
- [x] 2.5 RED `test_db.py::test_significance_for_date` — verdicts across 2 UTC days -> query returns only matching day
- [x] 2.6 GREEN `significance_for_date(connection, target_date)` — join `items`+`item_significance` filtered on `published_at`
- [x] 2.7 RED `test_db.py::test_unclassified_for_date` — mix of classified/unclassified items -> only unclassified returned
- [x] 2.8 GREEN `unclassified_for_date(connection, target_date)` — `LEFT JOIN item_significance WHERE label IS NULL`
- [x] 2.9 RED `test_db.py::test_clear_significance` — after `clear_significance`, item reappears in `unclassified_for_date`
- [x] 2.10 GREEN `clear_significance(connection)` — `DELETE FROM item_significance`
- [x] 2.11 (added, not in original list) RED/GREEN `significance_for_item(connection, item_id)` — closes `specs/item-storage/spec.md` "Query by item id returns its verdict" scenario

## Phase 3: Pure deterministic scorer (`synthesis/filter.py`, NEW) — Req: Deterministic Auto-Keep / Deterministic Drop

- [x] 3.1 RED `test_filter.py::test_score_p1_auto_keep` — `source_priority <= cfg.filter_keep_priority` -> `SIGNIFICANT`, no I/O
- [x] 3.2 GREEN create `synthesis/filter.py`: `Verdict(StrEnum)` = `SIGNIFICANT`/`ROUTINE`, `Mode(StrEnum)` = `DETERMINISTIC`/`LLM`, frozen `Significance(item_id, label, mode, model)`; `score(item, cfg)` P1 rule
- [x] 3.3 RED `test_filter.py::test_score_noise_keyword_drop` — title/summary matches `NOISE_KEYWORDS` -> `ROUTINE`
- [x] 3.4 GREEN add module-level `NOISE_KEYWORDS` default list + keyword-match branch
- [x] 3.5 RED `test_filter.py::test_score_uncertain` — neither rule matches -> `None`
- [x] 3.6 GREEN `score()` falls through to `return None` (UNCERTAIN)

## Phase 4: LLM verdict step — prompt + tolerant parser — Req: LLM Verdict for Uncertain Items / Tolerant Parsing with Safe Default

- [x] 4.1 RED `test_filter.py::test_parse_verdict_significant_and_routine` — case/whitespace/substring tolerant match for both words
- [x] 4.2 GREEN `parse_verdict(text)` — normalize + substring match
- [x] 4.3 RED `test_filter.py::test_parse_verdict_malformed_defaults_routine` — unparseable/ambiguous string -> `ROUTINE` (locked safe default)
- [x] 4.4 GREEN `parse_verdict()` default branch -> `ROUTINE`
- [x] 4.5 RED `test_filter.py::test_build_prompt_contains_item_and_instruction` — prompt includes title/summary + exact-one-word `SIGNIFICANT`/`ROUTINE` instruction
- [x] 4.6 GREEN `build_prompt(item)` string template

## Phase 5: Orchestrator `classify_items` (`synthesis/filter.py`) — Req: LLM Verdict / Run-Level Fallback / Idempotent Classification

- [x] 5.1 RED `test_filter.py::test_classify_llm_significant_and_routine` — fake `LLMClient` returns canned text -> `Significance(label, mode=LLM, model=resp.model)`
- [x] 5.2 GREEN `classify_items(items, llm_client, cfg)` — `score()` first; UNCERTAIN -> `llm_client.generate(build_prompt(item))` -> `parse_verdict` -> `Significance(mode=LLM)`
- [x] 5.3 RED `test_filter.py::test_classify_malformed_llm_output_routine` — malformed LLM text -> `ROUTINE`, `mode=LLM`
- [x] 5.4 RED `test_filter.py::test_classify_llm_error_degrades_whole_run` — fake client raises `LLMError` on the 1st of 3 UNCERTAIN items -> run completes, all 3 get `ROUTINE`/`DETERMINISTIC`, client called exactly once (never again)
- [x] 5.5 GREEN `classify_items` try/except `LLMError` -> flip `llm_available=False`, emit `ROUTINE`/`DETERMINISTIC` for the failing item and every subsequent UNCERTAIN item; never `SIGNIFICANT` by default; run never raises
- [x] 5.6 RED `test_filter.py::test_classify_pure_no_db_side_effects` — `classify_items` takes/returns plain lists, no storage import (idempotent-skip is caller's responsibility via `unclassified_for_date`)

## Phase 6: Rendering — two buckets (`storage/records.py`) — Req: Two-Bucket Rendering / Set-Aside Compact / Markdown Record Generation / Category Grouping

- [x] 6.1 RED `test_records.py::test_render_two_buckets_populated` — significant + set-aside items -> both sections present with correct items
- [x] 6.2 GREEN change signature to `render_markdown(significant, set_aside, target_date, mode)`; `## Significant` keeps existing category grouping/priority sort; `## Set aside` new compact section
- [x] 6.3 RED `test_records.py::test_render_empty_bucket_still_renders_header` — zero set-aside items -> `## Set aside` heading + `_(none)_` still present
- [x] 6.4 GREEN empty-bucket branch emits heading + `_(none)_` placeholder (applies to either bucket)
- [x] 6.5 RED `test_records.py::test_render_set_aside_compact_omits_summary` — routine item with non-empty summary -> line has no summary text beneath
- [x] 6.6 GREEN set-aside loop reuses item-line format, omits `item.summary` line
- [x] 6.7 RED `test_records.py::test_render_header_filter_mode` — header suffix `(filter: hybrid)` vs `(filter: deterministic-only — LLM unavailable)`
- [x] 6.8 GREEN header line appends mode suffix from `mode` param

## Phase 7: CLI wiring (`cli.py`) — Req: LLM Verdict / Run-Level Fallback / Idempotent Classification (end-to-end)

- [x] 7.1 RED update `tests/integration/test_collect_integration.py` — inject fake `LLMClient`, assert both buckets + mode header render end-to-end; update calls to new `render_markdown`/`_write_daily_records` signatures
- [x] 7.2 GREEN in `collect()`: after `db.upsert_items`, build `OllamaClient(config.ollama_url, config.ollama_model, config.ollama_timeout_seconds)`; fetch `db.unclassified_for_date(connection, today)`; `classify_items(...)`; persist via `db.upsert_significance(connection, verdicts)`
- [x] 7.3 GREEN update `_write_daily_records`: per kept date, use `db.significance_for_date` to split `items_for_date` into significant/set-aside lists; pass this run's `mode` (`hybrid` if `llm_available` else `deterministic-only`) to `records.render_markdown`
- [x] 7.4 (added, not in original list) RED/GREEN `tests/integration/test_collect_integration.py::TestWriteDailyRecordsMissingVerdict` — the mandated edge case: a historical in-window day's items with no significance row default to `ROUTINE`/set-aside instead of crashing

## Phase 8: Final Gates

- [x] 8.1 Run full `uv run pytest` — all green (131 passed)
- [x] 8.2 Run `uv run ruff check .` — clean
- [x] 8.3 Cross-check every scenario in `specs/hybrid-filter/spec.md`, `specs/daily-record/spec.md` (delta), `specs/item-storage/spec.md` (delta) has a corresponding passing test — done; one gap found and closed (see 2.11)
