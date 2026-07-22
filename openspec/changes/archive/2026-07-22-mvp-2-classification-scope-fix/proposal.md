# Proposal: MVP-2 Classification Scope Fix

## Intent

The hybrid filter is inert in normal use. `collect` classifies only items whose
`published_at` equals the UTC run-day, but feed items carry prior-day dates —
so `classify_items` receives an empty list, `item_significance` stays empty, and
every rendered item falls to `## Set aside`. Live run: 3105 items, 0 classified.
The classification scope (one day) does not match the render scope (7-day
window). Fix now: the feature ships broken for real feeds, and the operator gets
no feedback to notice it.

## Root Cause

- `cli.py::collect()` scopes classification to `db.unclassified_for_date(conn, today)`
  where `today = datetime.now(UTC).date()`; the query filters
  `published_at LIKE '{today}%'`.
- Feed `published_at` values are mostly prior days → the query returns nothing →
  0 verdicts. `_write_daily_records` renders a 7-day window, so full days render
  with no verdicts. Fixtures dated items on the run-day and missed it.
- Secondary: `collect` emits no summary; per-source failures are log-only with
  no logging configured — the operator validates blind.

## Scope

### In Scope
- Align classification scope to the render window: classify all UNCLASSIFIED
  items whose `published_at` falls within the window `_write_daily_records`
  renders, then render.
- New/changed storage query for window-scoped unclassified items (mirrors
  `unclassified_for_date`; exact signature decided in design).
- Preserve persist-once idempotency (classify only unclassified).
- Run feedback: concise end-of-run `typer.echo` summary + surface swallowed
  per-source failures via configured logging output.
- Regression test with items dated in the PAST (within window).

### Out of Scope
- Full structured logging / source-health dashboard (v1.0).
- Progress-bar framework (a summary suffices).
- Changes to deterministic rules, LLM prompt, collection, weekly briefing,
  scheduling.
- LLM-cost optimization: first real run classifies the in-window backlog
  (possibly hundreds of LLM calls for uncertain items); later runs are cheap via
  idempotent persistence. Document, do not optimize.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `hybrid-filter`: classification scope is the render window, not the UTC
  run-day — correct the requirement/scenarios accordingly.
- `item-storage`: add window-scoped unclassified query (day-scoped
  `unclassified_for_date` alone is insufficient).
- `collect-cli`: `collect` emits a run summary and surfaces per-source failures.

## Approach

1. Compute the render window bounds (design reads `records.dates_within_window`
   and `config.record_window_days`).
2. Add a storage query returning unclassified items within that window (e.g.
   `unclassified_within(conn, start, end)` or `unclassified_since(conn, cutoff)`;
   design picks signature, mirroring `unclassified_for_date`).
3. Classify the window-scoped unclassified set, upsert verdicts, THEN render —
   so every rendered item has a verdict.
4. Emit a `typer.echo` summary: sources queried, sources returning nothing/
   failing, items collected, items after dedup, items classified this run split
   Significant/Set aside, and filter mode (LLM-assisted vs deterministic-only).
5. Configure logging output (`logging.basicConfig(level=INFO)` at top of
   `collect`, or a `--verbose` flag — design decides) to surface swallowed
   per-source warnings.

## Key Decisions

1. Classification scope = render window (not UTC run-day).
2. New/changed DB query for window-scoped unclassified items.
3. Idempotency preserved (classify only unclassified).
4. Feedback via `typer.echo` summary + logging output; scope-limited (not v1.0
   structured logging).
5. Regression test uses items dated in the PAST (yesterday / earlier in window)
   — the case fixtures previously missed.

## Testing Plan (mandatory)

- Item published yesterday (within window) → gets classified + lands in the
  correct bucket.
- Item published outside the window → not classified.
- Idempotent re-run: already-classified items are skipped.
- Run summary reflects real counts (collected, deduped, classified split).
- Deterministic-only mode reported in the summary when the LLM is unavailable.

Runner: `uv run pytest`. Lint: `uv run ruff check .`. Strict TDD.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/cli.py` | Modified | Window-scoped classification; run summary; logging config |
| `src/ai_observatory/db.py` | Modified | Add window-scoped unclassified query |
| `tests/` | New/Modified | Past-dated regression, idempotency, summary, deterministic-only |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| First run triggers large LLM backlog (hundreds of calls) | High | Documented; deterministic rules pre-filter; idempotency makes later runs cheap; run-level LLM fallback already exists |
| Window/render bounds drift out of sync again | Med | Both derive from the same `record_window_days`/`dates_within_window` source in design |
| Summary counts miscount deduped vs classified | Low | Explicit test asserts real counts |

## Rollback Plan

Revert the branch `fix/mvp-2-classification-scope`. No schema migration or data
change is required — the new query is additive and verdicts are idempotent, so
reverting restores prior (day-scoped) behavior with no cleanup.

## Dependencies

- Existing `records.dates_within_window`, `config.record_window_days`,
  `item_significance` table, and run-level LLM fallback (all present).

## Success Criteria

- [ ] A `collect` run over real feeds classifies in-window items (non-zero
      Significant/Set aside split in rendered records).
- [ ] Re-running `collect` reclassifies nothing already classified.
- [ ] The run prints a summary with real counts and the active filter mode.
- [ ] Per-source failures appear in the operator's output.
- [ ] Regression test with past-dated items passes.

## Size / PR Forecast (budget 800)

Low-to-medium. Estimated ~200-350 changed lines across `cli.py`, `db.py`, and
tests — well within the 800-line review budget. Single PR is appropriate; no
chaining needed. `400-line budget risk: Low`.
