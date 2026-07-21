# Design: MVP-2 Hybrid Daily Filter

## Technical Approach

A pure `synthesis/filter.py` classifies each survivor as `SIGNIFICANT` or
`ROUTINE`. Deterministic rules decide the obvious cases; the injected
`LLMClient` port decides only UNCERTAIN survivors. Verdicts persist in a new
`item_significance` table so windowed re-renders never re-invoke the LLM.
`collect` runs the filter after `upsert_items`, before render. On the first
`LLMError` the whole run degrades to deterministic-only and never fails.
Satisfies every requirement in `specs/hybrid-filter/spec.md`.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|---|---|---|---|
| Filter home | pure `synthesis/filter.py` | logic in `daily.py`/cli | zero-network TDD via injected port; mirrors adapter seam |
| Trigger | inside `collect` | new `synthesize` CLI | roadmap parks CLI in MVP-3; keeps manual `collect` |
| Verdict lifetime | persisted | transient at render | 7-day regeneration would re-run LLM weekly; keeps re-renders deterministic |
| Storage shape | separate `item_significance` table | column on `items` | `items` is `INSERT OR IGNORE` immutable; verdicts must UPDATE + stay re-runnable |
| LLM contract | per-item one-word verdict + tolerant parser | JSON/batch | small models unreliable at JSON; adapter has no `format` passthrough; per-item isolates failure |
| Safe default | `ROUTINE` (set-aside) | keep-biased | UNCERTAIN items already failed the keep rules; ambiguous→set-aside keeps the Significant bucket high-precision. Items are preserved in Set aside, not lost, so recall is intact |
| Fallback | run-level, total, never-fail | per-item retry | server-down would raise N timeouts; one switch avoids the storm |

## Interfaces / Contracts

```python
class Verdict(StrEnum):          # SIGNIFICANT, ROUTINE
class Mode(StrEnum):             # DETERMINISTIC, LLM

@dataclass(frozen=True)
class Significance:
    item_id: str
    label: Verdict
    mode: Mode
    model: str | None            # populated only when mode == LLM

# Pure deterministic scorer — three-way, no I/O:
def score(item: Item, cfg: Config) -> Verdict | None
#   source_priority <= cfg.filter_keep_priority -> SIGNIFICANT
#   noise keyword in title/summary            -> ROUTINE
#   else                                       -> None (UNCERTAIN)

# Pure parser — tolerant, safe default ROUTINE:
def parse_verdict(text: str) -> Verdict     # normalize, substring, else ROUTINE

def build_prompt(item: Item) -> str         # "...exactly one word: SIGNIFICANT or ROUTINE"

# Orchestrator — deterministic first, LLM only on UNCERTAIN survivors:
def classify_items(items, llm_client, cfg) -> list[Significance]
```

Keyword lists (`NOISE_KEYWORDS`) live as module defaults in `filter.py`
(config is scalar-only). New config: `filter_keep_priority` (default 1) via
`AIOBS_FILTER_KEEP_PRIORITY`, using existing `_int_env`.

### Degradation control flow

```
llm_available = True
for item in items:
    det = score(item, cfg)
    if det is not None:                     # KEEP or DROP by rule
        emit Significance(det, DETERMINISTIC); continue
    if not llm_available:                   # already degraded
        emit Significance(ROUTINE, DETERMINISTIC); continue
    try:
        resp = llm_client.generate(build_prompt(item))
        emit Significance(parse_verdict(resp.text), LLM, resp.model)
    except LLMError:                        # FIRST failure only
        log.warning("LLM unavailable; run degraded to deterministic-only")
        llm_available = False
        emit Significance(ROUTINE, DETERMINISTIC)   # never SIGNIFICANT
# run always completes; header reflects llm_available
```

## Data Flow

```
items ─► score() ─► KEEP ─────────────┐
                 ─► DROP ─────────────┤
                 ─► UNCERTAIN ─► LLM ──┤ (or ROUTINE if degraded)
                                       ▼
                          list[Significance] ─► db.upsert_significance
                                       ▼
   items + verdicts ─► render_markdown(significant, set_aside, mode)
```

## Persistence Design (`storage/db.py`)

```sql
CREATE TABLE IF NOT EXISTS item_significance (
    item_id TEXT PRIMARY KEY REFERENCES items(id),
    label TEXT NOT NULL,
    mode TEXT NOT NULL,
    model TEXT,
    classified_at TEXT NOT NULL
);
```
Additive to `_SCHEMA` (idempotent `CREATE TABLE IF NOT EXISTS`; existing DBs
tolerate it). New helpers:
- `upsert_significance(conn, rows)` — `INSERT ... ON CONFLICT(item_id) DO UPDATE`.
- `unclassified_for_date(conn, date)` — `items` LEFT JOIN `item_significance`
  WHERE `label IS NULL` → only new survivors go to `classify_items`.
- `significance_for_date(conn, date)` — verdicts for render.
- `clear_significance(conn)` — reclassify path for threshold tuning.

Idempotency: normal runs classify only unclassified rows, respecting the
existing `INSERT OR IGNORE` model and 7-day windowed regeneration.

## CLI Wiring (`cli.py`)

In `collect`, after `db.upsert_items`, before `_write_daily_records`: build
`OllamaClient(config.ollama_url, config.ollama_model, config.ollama_timeout_seconds)`;
for `today`, fetch `unclassified_for_date`, call `classify_items`, persist via
`upsert_significance`. `_write_daily_records` reads verdicts, splits day items
into two buckets, passes `mode` (hybrid vs deterministic-only) to render.

## Rendering (`storage/records.py`)

`render_markdown(significant, set_aside, target_date, mode)`. Header:
`# <date> (filter: hybrid)` or `(filter: deterministic-only — LLM unavailable)`.
`## Significant` keeps existing category grouping/sort; `## Set aside` is a
compact list. Empty buckets render the heading with an `_(none)_` line.

## Decision / Failure-Mode Table

| Case | label | mode | LLM called |
|---|---|---|---|
| P1 source | SIGNIFICANT | deterministic | no |
| noise keyword | ROUTINE | deterministic | no |
| uncertain, LLM says SIGNIFICANT | SIGNIFICANT | llm | yes |
| uncertain, LLM says ROUTINE | ROUTINE | llm | yes |
| uncertain, malformed output | ROUTINE (default) | llm | yes |
| uncertain, first LLMError | ROUTINE | deterministic | yes (fails once) |
| uncertain after degrade | ROUTINE | deterministic | no |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit `test_filter.py` (NEW) | scorer keep/drop/uncertain; parser tolerant+default; run-level fallback never fails | fake `LLMClient` returning canned verdicts or raising `LLMError`; pure scorer needs no LLM |
| Unit `test_records.py` (MOD) | two-bucket render, header modes, empty buckets | pure |
| Unit `test_config.py` (MOD) | `AIOBS_FILTER_*` default + override | env |
| Integration `test_db.py` (MOD) | upsert/query-unclassified/clear idempotency | in-memory sqlite |

Never live Ollama. Fallback never-fail is a mandatory RED test.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. The only external call is the
existing injected `LLMClient` port over HTTP, already typed and error-bounded.

## File Changes

| File | Action | Description |
|---|---|---|
| `synthesis/filter.py` | Create | pure scorer + parser + `classify_items` orchestrator |
| `config.py` | Modify | `filter_keep_priority` via `AIOBS_FILTER_KEEP_PRIORITY` |
| `storage/db.py` | Modify | `item_significance` schema + upsert/query/clear |
| `storage/records.py` | Modify | two-bucket render + mode header |
| `cli.py` | Modify | classify after upsert; build `OllamaClient`; feed buckets |
| `tests/unit/test_filter.py` | Create | scorer, parser, fallback |
| `tests/unit/test_records.py`, `test_config.py`, `tests/integration/test_db.py` | Modify | buckets, config, persistence |

## Non-Goals

Source expansion, `synthesize --daily/--weekly` CLI, weekly briefing,
scheduling, LLM JSON/batch mode, retry/backoff. Explicitly out of scope.

## Migration / Rollout

Additive `CREATE TABLE IF NOT EXISTS`; frozen `items` untouched. Rollback:
revert branch; table unused if `filter.py` removed; `data/` gitignored.

## Open Questions

None — spec locks safe default (`ROUTINE`), fallback granularity (run-level),
and storage shape (separate table).
