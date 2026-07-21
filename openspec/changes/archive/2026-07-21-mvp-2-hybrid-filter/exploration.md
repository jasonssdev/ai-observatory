# Exploration: MVP-2 slice 2 — Hybrid daily filter (signal vs noise)

> Filesystem mirror of Engram artifact `sdd/mvp-2-hybrid-filter/explore` (id 1444),
> written by the propose phase because the explore executor had no Write tool.

Central slice of MVP-2 per `docs/roadmap.md` (lines 35-51) and `docs/architecture.md`
(Synthesis layer, lines 146-153). Turns the raw daily record into a CURATED one:
deterministic rules first (source priority + keyword thresholds) drop obvious noise,
then the local LLM (`OllamaClient`, built in mvp-2-ollama-adapter) classifies survivors.
On any `LLMError` the run falls back to deterministic-only and MUST NOT fail. Source
expansion (HF/HN/P2), weekly briefing, and scheduling are OTHER MVP-2/3 slices — OUT of
scope here.

## Current State (code reality)
- `synthesis/llm.py` DONE: `OllamaClient.generate(prompt) -> LLMResponse(text, model, raw:dict)`; RAISES typed `LLMError` (`LLMUnavailableError`, `LLMTimeoutError`, `LLMModelNotFoundError`, `LLMResponseError`) — never swallows. Prompt-in/text-out, format-agnostic (no `format`/`options` passthrough). So structured-output + verdict PARSING lands in THIS slice.
- `storage/models.py`: `Item` is a `@dataclass(frozen=True)` — id, title, url, source, source_priority(int 1/2/3), category, published_at, collected_at, summary, raw. No numeric score field (upvotes/points are the source-expansion slice, not here). Deterministic signals available NOW = source_priority + keyword match on title/summary + category.
- `storage/db.py`: `items` table, `upsert_items` = `INSERT OR IGNORE` (items immutable once written; re-runs never update them). `items_for_date(conn, date)` via `published_at LIKE`. Indexed on published_at + source_priority. No significance column.
- `storage/records.py`: `render_markdown(items, date)` groups by fixed `_CATEGORY_ORDER`, sorts priority asc + published_at desc, header `# <date> (N items)`. Single flat bucket today.
- `cli.py`: `collect` = load sources -> collect -> `dedup_batch` -> `db.upsert_items` -> `_write_daily_records` (full-regeneration over a `record_window_days` window, default 7). No `synthesize` command yet. Filtering has NO home yet.
- `config.py`: frozen `Config.from_env()`, `AIOBS_*` scalars, `_int_env`/`_float_env` fail-safe helpers. Ollama settings already present (`ollama_url`, `ollama_model=llama3.2`, `ollama_timeout_seconds=60.0`). Scalar env only — no list/keyword env support yet.
- Roadmap at-a-glance: MVP-2 "Runs automatically? No — manual"; `synthesize --daily/--weekly` CLI + scheduling are explicitly MVP-3. So the curated record must be produced within the existing manual `collect` in this slice.

## Affected Areas
- `src/ai_observatory/synthesis/filter.py` — NEW. Pure deterministic+LLM classification: `Significance` enum (SIGNIFICANT/ROUTINE), deterministic scorer (priority+keywords -> keep/drop/uncertain), LLM verdict prompt+parser, run-level degradation. No I/O beyond the injected `LLMClient` port.
- `src/ai_observatory/config.py` — MODIFY. Add threshold config (e.g. `AIOBS_FILTER_*`). Keyword lists likely stay as module defaults in filter.py (scalar-only env).
- `src/ai_observatory/storage/db.py` — MODIFY (if persisted). New `item_significance` table + upsert/query, or a nullable column on `items`.
- `src/ai_observatory/storage/records.py` — MODIFY. Render two buckets (Significant / Set aside) + a filter-mode signal in the header.
- `src/ai_observatory/cli.py` — MODIFY. Wire the filter into `collect` (build `OllamaClient` from config, classify after upsert, before render).
- `tests/unit/test_filter.py` — NEW. Deterministic rule behavior, thresholds, LLM verdict parsing (tolerant), LLMError -> deterministic fallback (run must not fail), malformed LLM output.
- `tests/unit/test_records.py`, `tests/unit/test_config.py`, `tests/integration/*` — MODIFY for buckets + thresholds + end-to-end.
- NOT here: `synthesize --daily` CLI (MVP-3), weekly, sources.yaml expansion, HF/HN score sources.

## Key open questions (for the proposal to resolve)
1. **Filter module location** — dedicated `synthesis/filter.py` (pure, unit-testable) vs put it in `synthesis/daily.py`. Architecture calls `daily.py` "filter + classify". Recommend `filter.py` = pure classification; a thin `daily.py`/collect orchestration consumes it. Keeps LLM-free deterministic logic trivially testable.
2. **Where filtering runs** — inside `collect` (recommended for MVP-2: stays "manual `collect`", produces the curated record now) vs a new `filter`/`synthesize --daily` command (roadmap parks `synthesize --daily` in MVP-3). Recommend: insert into the collect pipeline after upsert, before render.
3. **Significance: persisted vs transient** — THE central trade-off (see Approaches). Render is full-regeneration over a 7-day window each run; transient classification re-invokes the LLM for a week of items every `collect` (slow/costly, non-deterministic records). Persisted classify-once fits the existing idempotent-upsert model.
4. **Storage shape if persisted** — separate `item_significance` table (item_id PK/FK, verdict, method, classified_at) vs a column on `items`. `items` upsert is `INSERT OR IGNORE` (immutable), and classification happens AFTER insert and must be re-runnable during tuning — a column fights both. Recommend a separate table (keeps frozen `Item` pure; UPDATE-able verdicts).
5. **Deterministic scoring model** — P1 -> auto-significant ("clear the bar easily"), noise-keyword match -> drop, else UNCERTAIN -> LLM. Three-way outcome (KEEP/DROP/UNCERTAIN) realizes "rules first to drop obvious noise, then LLM on survivors". Thresholds via env; keyword lists as tunable module defaults.
6. **LLM output contract + parsing** — constrained one-word verdict ("Respond with exactly one word: SIGNIFICANT or ROUTINE") + tolerant parser (normalize, substring match, safe default on ambiguity) vs JSON output. Small local models are unreliable at raw JSON and the adapter has no `format:"json"` passthrough. Recommend constrained-verdict + tolerant parsing; note optional adapter `format` extension as an alternative. Per-item classification (robust, isolates failure) vs batch (fewer calls, fragile parsing) — recommend per-item.
7. **Fallback granularity + signal** — per-item try/except is simple but if the server is down every survivor raises (N timeouts, slow). Recommend RUN-LEVEL degradation: on first `LLMError`, log once, switch the whole run to deterministic-only, classify remaining survivors by rules. Record signals mode in header, e.g. `(filter: hybrid)` vs `(filter: deterministic-only — LLM unavailable)`. The run MUST NOT fail — central resilience requirement.
8. **Two-bucket rendering** — top-level `## Significant` and `## Set aside` sections (significant still category-grouped; set-aside as a compact list). Modifies the mvp-1 daily-record spec (header count, grouping) and adds a new hybrid-filter capability.
9. **Tuning re-classification** — roadmap: "tune thresholds and the prompt until it feels right". Persisted verdicts need a way to force re-classification (clear table / `--reclassify` flag). Classify only rows where verdict IS NULL / absent on normal runs.

## Approaches
1. **Hybrid filter in `synthesis/filter.py`, wired into `collect`, verdicts persisted in a separate `item_significance` table, two-bucket render, run-level deterministic fallback (RECOMMENDED)** — pure deterministic+LLM logic is fully TDD-able with an injected `LLMClient` mock; classify-once fits idempotent upsert + windowed regeneration; separate table keeps frozen `Item` pure and verdicts UPDATE-able; run-level fallback avoids N timeouts; stays "manual `collect`"; deterministic records on re-render. Cons: new-table migration; more moving parts; stale verdicts need a reclassify path. Effort: Medium.
2. **Transient classification at render time (no persistence)** — no migration, always reflects current thresholds, but re-invokes the LLM for a week of items EVERY `collect` (slow/costly, non-deterministic records); conflicts with idempotency/stable-re-run spec. Effort: Low-Medium, poor fit.
3. **Significance column on `items`** — single table, but fights the `INSERT OR IGNORE` immutable-item model and pollutes the frozen `Item` with derived metadata. Effort: Medium.
4. **Batch-classify all survivors in one prompt + JSON** — fewer calls, but one malformed line poisons the batch; small models unreliable at JSON without `format` passthrough. Rejected for MVP-2; future optimization. Effort: Medium-High.
5. **New `synthesize --daily` CLI now** — rejected: roadmap parks `synthesize --daily/--weekly` + scheduling in MVP-3. Keep filtering inside manual `collect` for MVP-2.

## Recommendation
Approach 1. Pure `synthesis/filter.py` (deterministic scorer + LLM verdict parser + run-level degradation) depending on the `LLMClient` port; wire into `collect` after `upsert_items`, before render. Persist verdicts in a separate `item_significance` table, classifying only unclassified survivors. Deterministic layer = P1 auto-keep, noise-keyword drop, else UNCERTAIN->LLM. LLM = constrained one-word verdict + tolerant parser, per-item. On the first `LLMError`, degrade the whole run to deterministic-only and mark the record header; never fail. Render `## Significant` + `## Set aside`. Provide a reclassify path for tuning. Defer JSON/batch output, `format` passthrough, `synthesize --daily` CLI, retries, and source expansion.

## Risks
- **Idempotency vs LLM cost**: transient classification over the windowed regeneration would re-run the LLM for a week of items each `collect`. Persist-and-skip-classified is the mitigation; the proposal must lock this.
- **Small-model verdict reliability**: local models drift from "one word"; the tolerant parser + safe default (and the deterministic fallback) are mandatory, with explicit malformed-output tests.
- **Fallback must be total**: any `LLMError` must degrade to deterministic-only without aborting the run — a required resilience test.
- **Storage migration**: adding `item_significance` is a schema change; `db.connect` runs `_SCHEMA` idempotently (`CREATE TABLE IF NOT EXISTS`), so an additive table is safe, but existing DBs must tolerate it.
- **Keyword config surface**: config.py is scalar-only; keyword lists as module defaults for MVP-2 is acceptable but a known limitation.
- **Spec delta**: the mvp-1 daily-record spec (header count, single grouping) is MODIFIED by two-bucket rendering; add a hybrid-filter capability.

## Ready for Proposal
Yes. Scope is tight and roadmap-bounded.
