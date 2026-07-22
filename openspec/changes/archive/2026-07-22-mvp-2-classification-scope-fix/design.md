# Design: MVP-2 Classification Scope Fix

## Technical Approach

`collect()` currently classifies only `unclassified_for_date(today)` while `_write_daily_records` renders a multi-day window, so real feeds (prior-day dates) get zero verdicts. Fix: introduce a **single source of truth for the window** (`records.window_start`), add a **window-scoped** unclassified query mirroring `unclassified_for_date`, and swap `collect()` to classify the exact render window. Add a `typer.echo` run summary and enable logging so per-source empties/failures surface. No collector, prompt, rule, or schema change.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|---|---|---|---|
| Query shape | `unclassified_within(conn, start_date, end_date)` — start inclusive, end **exclusive** (`date` args) | `unclassified_since(conn, cutoff)` | Bounding both ends excludes future-dated items, matching render (`dates_within_window` drops `d > today`). `_since` would classify future items (wasted, inconsistent). |
| Window source of truth | New `records.window_start(today, window_days) -> date` = `today - timedelta(days=window_days)`; `dates_within_window` refactored to call it; `collect` calls it too | Recompute `today - window_days` inline in `collect` | Removes the drift risk — render bound and classify bound derive from one function. |
| Future-date handling | Exclude (do not classify or render) | Classify+render future | Consistency: `dates_within_window` already excludes `d > today`; classification must not diverge. |
| ISO string range | `published_at >= start.isoformat()` AND `published_at < end.isoformat()` | `LIKE` per day / BETWEEN | ISO-8601 is lexicographically sound. `start='2026-07-14'` ≤ `'2026-07-14T..'`; exclusive `end=(today+1).isoformat()='2026-07-22'` excludes `'2026-07-22T..'` yet includes all of today. |
| Per-source feedback | Count empty returns in the collect loop + `logging.basicConfig(level=INFO)` | Change collectors to signal failures; add `--verbose` | Least-invasive: preserves the never-raise/return-`[]` collector contract; existing `logger.warning` calls become operator-visible. |

## Data Flow

    sources → collectors.collect() → collected_items → dedup_batch → deduped_items
                     │ (per-source len==0 → empty count)              │
                     ▼                                          upsert_items
              logging.INFO warnings                                   │
                                                        window_start(today, window_days)
                                                                      ▼
                                       unclassified_within(conn, start, today+1)
                                          → classify_items → upsert_significance
                                                                      ▼
                                            _write_daily_records (same window)
                                                                      ▼
                                                    typer.echo run summary

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/storage/records.py` | Modify | Add `window_start(today, window_days) -> date`; `dates_within_window` uses it. |
| `src/ai_observatory/storage/db.py` | Modify | Add `unclassified_within(conn, start_date, end_date)` mirroring `unclassified_for_date` column selection + `_row_to_item`. |
| `src/ai_observatory/cli.py` | Modify | Compute window via `records.window_start`; replace `unclassified_for_date(today)` with `unclassified_within`; count per-source empties; `logging.basicConfig(INFO)`; emit summary. |
| `tests/integration/test_db.py` | Modify | `unclassified_within` boundary/exclusion tests. |
| `tests/integration/test_collect_integration.py` | Modify | Past-dated regression + summary-output assertions. |

## Interfaces / Contracts

```python
# db.py
def unclassified_within(
    connection: sqlite3.Connection, start_date: date, end_date: date
) -> list[Item]:
    """Unclassified items with start_date <= published_at < end_date (UTC)."""
    cursor = connection.execute(
        f"SELECT {_SELECT_COLUMNS} FROM items "
        "LEFT JOIN item_significance ON item_significance.item_id = items.id "
        "WHERE item_significance.label IS NULL "
        "AND items.published_at >= ? AND items.published_at < ? "
        "ORDER BY items.published_at",
        (start_date.isoformat(), end_date.isoformat()),
    )
    return [_row_to_item(row) for row in cursor.fetchall()]

# records.py
def window_start(today: date, window_days: int) -> date:
    return today - timedelta(days=window_days)
```

`collect()` control flow (order): `upsert_items` → `today` → `start = records.window_start(today, config.record_window_days)`; `end = today + timedelta(days=1)` → `unclassified_within(conn, start, end)` → `classify_items` → `upsert_significance` → `mode` → `candidate_dates` → `_write_daily_records`. Per-source loop records `empty_sources += 1` when `collector.collect(source)` returns `[]`.

Summary echo lines (after render):

```
Sources queried: {sources_queried}
Sources returning nothing: {empty_sources}
Items collected: {len(collected_items)}
Items after dedup: {len(deduped_items)}
Items classified this run: {n} (significant: {sig}, set aside: {routine})
Filter mode: {mode}
```

`n = len(verdicts)`; `sig = sum(v.label == Verdict.SIGNIFICANT for v in verdicts)`; `routine = n - sig`.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Integration (db) | `unclassified_within`: returns only unclassified in-range; excludes classified + out-of-range; `start` inclusive, `today` inclusive, day-before excluded, future-dated excluded | `:memory:` sqlite, items across dates |
| Integration (collect) | **Regression**: freeze `today`=2026-07-21 so `feed_hybrid_filter.xml` (07-20) items are *yesterday*/in-window → assert they get verdicts and land in correct rendered bucket | reuse `_FakeFetcher` + `_FakeOllamaClient` + `_FixedToday` (shifted); no network/Ollama |
| Integration (collect) | Idempotent re-run classifies nothing already classified | second `collect()`, assert `_FakeOllamaClient.calls` unchanged |
| Integration (collect) | Summary reports real counts + mode; deterministic-only reported when LLM raises | capture `collect()` echo via `capsys`/`CliRunner`; fake LLM raising `LLMError` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. `logging.basicConfig` writes to stderr only.

## Migration / Rollout

No migration required. New query is additive; verdicts remain idempotent. Rollback = revert branch `fix/mvp-2-classification-scope`.

## Open Questions

- [ ] None blocking. First real run may issue a large in-window LLM backlog (documented in proposal; idempotency makes later runs cheap).
