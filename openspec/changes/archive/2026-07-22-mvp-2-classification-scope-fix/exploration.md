# Exploration: MVP-2 Classification Scope Fix (Root-Cause Diagnosis)

> Captured from real-usage validation of MVP-2 (a live `collect` run). This is a
> completed diagnosis, not open exploration — the root cause is confirmed by code
> and live DB inspection.

## Symptom

The hybrid filter classifies NOTHING in normal use. `item_significance` stays
empty; every rendered item falls to the `## Set aside` bucket via the
missing-verdict default. The filter is effectively inert.

## Root Cause (confirmed)

- `cli.py::collect()` (~lines 105-112) does:
  `today = datetime.now(UTC).date()` →
  `unclassified = db.unclassified_for_date(connection, today)` →
  `classify_items(unclassified, ...)` → `upsert_significance`.
- `db.unclassified_for_date(connection, target_date)` filters
  `WHERE items.published_at LIKE '{target_date}%'` — items PUBLISHED on the UTC
  run-day.
- RSS/Atom/JSON feed items carry their OWN `published_at` (mostly prior days),
  which almost never equals the UTC run-day.
- Live evidence: 3105 items collected, 692 published on 2026-07-21, ZERO on the
  run-day 2026-07-22 → `classify_items([])` → 0 verdicts → `item_significance`
  empty → `2026-07-21.md` rendered 0 Significant / 692 Set aside.
- Meanwhile `_write_daily_records` renders a 7-day window
  (`records.dates_within_window(...)`). The classification scope (one UTC day)
  and the render scope (7-day window) are MISMATCHED.
- This was flagged during the original hybrid-filter tasks phase as an "edge
  case" and wrongly deferred; it is the DOMINANT case. Fixture tests missed it
  because fixtures dated items on the run-day.

## Second, Related Defect

`collect` produces NO user feedback (no progress, no summary). Per-source
failures are swallowed by collectors (log-only) with no logging output
configured, so the operator validates blind.

## Affected Code

- `cli.py::collect()` — classification scope + missing run feedback.
- `db.py::unclassified_for_date` — day-scoped query; needs a window-scoped
  sibling.
- `records.dates_within_window` / `config.record_window_days` — the render
  window bounds classification must align to (design phase reads exact bounds).

## Affected Capabilities

- `hybrid-filter` — classification scope must be the render window, not run-day.
- `item-storage` — new window-scoped unclassified query.
- `collect-cli` — run summary + surfacing per-source failures.
