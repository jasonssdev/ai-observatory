# Delta for hybrid-filter

## ADDED Requirements

### Requirement: Classification Scope Matches the Render Window

During a `collect` run, classification MUST cover every unclassified item
whose `published_at` falls within the render window — the same window
`_write_daily_records` renders, bounded by `record_window_days` (mirroring
`records.dates_within_window`) — not only items published on the current
UTC run-day. Items already carrying a persisted verdict remain excluded per
Idempotent Classification (unchanged). Run-Level Fallback on LLM
Unavailability (unchanged) continues to govern degraded runs across this
wider scope.

#### Scenario: In-window item published on a prior day is classified

- GIVEN an unclassified item with `published_at` on a day before today but
  within the render window
- WHEN `collect` runs
- THEN the item is classified and receives a persisted significance verdict

#### Scenario: Out-of-window item is not classified

- GIVEN an unclassified item with `published_at` older than the render
  window
- WHEN `collect` runs
- THEN the item is not classified and receives no verdict

#### Scenario: Idempotency holds across the wider scope

- GIVEN an item within the render window that already has a persisted
  verdict
- WHEN `collect` runs again
- THEN the item is not reclassified and its stored verdict is unchanged

#### Scenario: Run-level LLM fallback holds across the wider scope

- GIVEN multiple UNCERTAIN items spread across several days within the
  render window, and an injected `LLMClient` whose first call raises an
  `LLMError`
- WHEN `collect` classifies the window-scoped unclassified set
- THEN the run completes without error and every remaining UNCERTAIN item
  in the window, regardless of its published date, is classified
  deterministically
