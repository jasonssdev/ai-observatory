# Proposal: MVP-2 Hybrid Daily Filter (signal vs noise)

## Intent

The daily record captures EVERYTHING collected (mvp-1) — signal and noise sit in one
flat list, so the human still triages by hand. This slice makes the record CURATED:
deterministic rules drop obvious noise and auto-keep high-signal sources; the local
LLM (`OllamaClient`, built in mvp-2-ollama-adapter) classifies only the uncertain
survivors as `SIGNIFICANT` vs `ROUTINE`. Fills the Synthesis-layer filter/classify slot
per `docs/architecture.md` (lines 146-153) and the MVP-2 core per `docs/roadmap.md`
(35-51). Hard resilience constraint: if the LLM is unavailable, the run degrades to
deterministic-only and MUST NOT fail.

## Scope

### In Scope
- NEW `src/ai_observatory/synthesis/filter.py`: pure classifier — `Significance` enum, deterministic scorer (P1 auto-keep / noise-keyword drop / else UNCERTAIN->LLM), LLM verdict prompt + tolerant parser, run-level degradation. No I/O beyond the injected `LLMClient` port.
- MODIFY `config.py`: `AIOBS_FILTER_*` threshold scalars (fail-safe helpers); keyword lists as tunable module defaults in `filter.py`.
- MODIFY `storage/db.py`: NEW `item_significance` table (`CREATE TABLE IF NOT EXISTS`) + upsert/query/clear; classify only unclassified survivors.
- MODIFY `storage/records.py`: two buckets (`## Significant` category-grouped, `## Set aside` compact) + filter-mode header signal.
- MODIFY `cli.py`: wire filter INTO `collect` after `upsert_items`, before render; build `OllamaClient` from config; add a reclassify path for threshold/prompt tuning.
- Tests: deterministic keep/drop, LLM verdict significant/routine, malformed output -> safe default, `LLMError` -> run-level deterministic-only (no failure), idempotent skip-classified, two-bucket render. All LLM via injected mock — never live Ollama.

### Out of Scope (non-goals)
- Source expansion (HF Daily Papers, HN Algolia, P2 feeds) — separate MVP-2 slice.
- `synthesize --daily/--weekly` CLI + weekly briefing + scheduling — MVP-3.
- LLM `format:"json"` / batch classification, retry/backoff — deferred.

## Capabilities

### New Capabilities
- `hybrid-filter`: deterministic-then-LLM significance classification of items; P1 auto-keep, noise-keyword drop, UNCERTAIN -> per-item LLM verdict; run-level graceful degradation to deterministic-only on any `LLMError` (run never fails).

### Modified Capabilities
- `daily-record`: two-bucket rendering (`## Significant` / `## Set aside`) + filter-mode header signal, replacing the single flat category-grouped list and `(N items)` header.
- `item-storage`: additive `item_significance` table (item_id FK, verdict, method, classified_at) with idempotent upsert, query-unclassified, and clear-for-reclassify; the frozen `items` table is untouched.

## Approach

Exploration **Approach 1**. Pure `synthesis/filter.py` depends only on the `LLMClient`
Protocol port — strict-TDD via an injected mock, mirroring the mvp-1/adapter seam
(zero network). Three-way deterministic outcome (KEEP / DROP / UNCERTAIN) drops noise
by rule and sends only survivors to the LLM. Verdicts persist in a separate
`item_significance` table so re-runs classify only NEW/unclassified survivors — bounding
LLM cost against the 7-day windowed full-regeneration and keeping re-rendered records
deterministic. Structured-output parsing lives HERE (the adapter is format-agnostic):
constrained one-word verdict + tolerant parser with a safe default. On the first
`LLMError`, degrade the WHOLE run to deterministic-only, log once, and signal mode in
the header. `records.py` renders two buckets.

### Key Decisions (resolves 9 open items)
| # | Decision |
|---|----------|
| 1 | **Filter location**: dedicated pure `synthesis/filter.py` (deterministic scorer + LLM verdict parser + degradation), consumed by the collect pipeline. Keeps LLM-free logic trivially unit-testable. |
| 2 | **Where it runs**: INSIDE existing `collect`, after `upsert_items`, before render. No new `synthesize --daily` CLI (that is MVP-3) — stays "manual `collect`". |
| 3 | **Persisted, not transient**: verdicts persisted so the 7-day windowed regeneration does NOT re-invoke the LLM each run; keeps re-renders deterministic. Transient rejected (slow/costly/non-deterministic). |
| 4 | **Separate `item_significance` table** (not a column on `items`): `items` is `INSERT OR IGNORE` immutable; verdicts must be UPDATE-able for tuning. Keeps frozen `Item` pure. |
| 5 | **Deterministic scoring**: P1 -> auto-SIGNIFICANT; noise-keyword match -> DROP; else UNCERTAIN -> LLM. Thresholds via `AIOBS_FILTER_*`; keyword lists as module defaults. |
| 6 | **LLM verdict contract**: per-item constrained one-word `SIGNIFICANT`/`ROUTINE`; TOLERANT parser (normalize, substring, safe default on ambiguity). JSON/batch rejected — small local models unreliable, adapter lacks `format` passthrough. |
| 7 | **Fallback**: RUN-LEVEL, total, never-fail. First `LLMError` degrades the whole run to deterministic-only; remaining survivors classified by rules. |
| 8 | **Two-bucket render**: `## Significant` (category-grouped) + `## Set aside` (compact) + header mode signal `(filter: hybrid)` / `(filter: deterministic-only — LLM unavailable)`. |
| 9 | **Reclassify path**: normal runs classify only rows absent from `item_significance`; a clear/reclassify path forces re-classification during prompt/threshold tuning. |

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/filter.py` | New | Pure classifier: deterministic scorer + LLM verdict parser + run-level degradation. |
| `src/ai_observatory/config.py` | Modified | `AIOBS_FILTER_*` threshold scalars. |
| `src/ai_observatory/storage/db.py` | Modified | `item_significance` table + upsert/query-unclassified/clear. |
| `src/ai_observatory/storage/records.py` | Modified | Two-bucket render + header mode signal. |
| `src/ai_observatory/cli.py` | Modified | Wire filter into `collect`; build `OllamaClient`; reclassify path. |
| `tests/unit/test_filter.py` | New | Deterministic + verdict + malformed + fallback + idempotent cases. |
| `tests/unit/{test_records,test_config}.py`, `tests/integration/*` | Modified | Buckets, thresholds, end-to-end. |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Fallback not total → run aborts when Ollama down | Med | Run-level degrade on first `LLMError`; mandatory never-fail test. |
| Small-model verdict drift (not one word) | High | Tolerant parser + safe default; explicit malformed-output test. |
| LLM re-run cost over 7-day window | Med | Persist verdicts; classify only unclassified survivors; idempotent-skip test. |
| Storage migration on existing DBs | Low | Additive `CREATE TABLE IF NOT EXISTS`; frozen `items` untouched. |
| Stale verdicts vs tuned thresholds | Med | Reclassify/clear path; documented tuning workflow. |
| Keyword lists in code, not env | Low | Accepted for MVP-2 (roadmap allows code-level tuning); noted limitation. |

## Rollback Plan
Additive feature slice. Revert the change branch; `item_significance` is additive and
unused if `filter.py` is gone. `data/` is gitignored — drop the table or delete
`data/observatory.db` to reset. No change to the frozen `items` table, no data unwind.

## Dependencies
None new. Reuses the existing `OllamaClient` (mvp-2-ollama-adapter), stdlib `sqlite3`.
Runtime prerequisite (not a code dep): a local Ollama server for integration/smoke —
never for unit tests (injected `LLMClient` mock).

## Success Criteria
- [ ] `collect` produces a curated record with `## Significant` / `## Set aside` buckets.
- [ ] P1 auto-kept; noise-keyword items set aside without an LLM call.
- [ ] Uncertain survivors classified by one-word LLM verdict; malformed output → safe default.
- [ ] Ollama down → header shows `deterministic-only`; run completes without error.
- [ ] Re-run classifies only new survivors; records stay deterministic.
- [ ] Reclassify path re-scores after threshold/prompt tuning.
- [ ] `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 800 changed lines)
Estimate ~520-680 changed lines: `filter.py` (~150-190), `db.py` delta (~60-80),
`records.py` delta (~50-70), `cli.py` delta (~40-60), `config.py` delta (~20),
`test_filter.py` (~180-220), records/config/integration deltas (~60-90). A storage
migration plus three capabilities (one new, two modified) pushes this to the upper-mid
band but stays under 800. `400-line budget risk: Medium` (exceeds the 400 default;
within the 800 session budget). `Chained PRs recommended: No` — single cohesive slice,
but a natural 2-PR split exists if review load is a concern: (1) pure `filter.py` +
`config` + tests, (2) storage table + `records` two-bucket + `cli` wiring. `Decision
needed before apply: No` under the 800-line budget.
