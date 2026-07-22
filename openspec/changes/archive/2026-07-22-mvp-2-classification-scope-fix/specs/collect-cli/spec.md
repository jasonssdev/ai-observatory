# Delta for collect-cli

## ADDED Requirements

### Requirement: End-of-Run Summary

`collect` MUST emit an end-of-run summary via `typer.echo` reporting:
sources queried, sources that returned nothing or failed, items collected,
items remaining after dedup, items classified during this run split into
significant/set-aside counts, and the active filter mode (`hybrid` or
`deterministic-only`).

#### Scenario: Summary reflects real run counts

- GIVEN a run that collects items from several sources, dedups them, and
  classifies a mix of significant and set-aside verdicts
- WHEN `collect` finishes
- THEN the printed summary's collected, deduped, and classified
  (significant/set-aside) counts match the actual run results

#### Scenario: Deterministic-only mode is reported

- GIVEN the `LLMClient` is unavailable during the run
- WHEN `collect` finishes
- THEN the printed summary reports the filter mode as
  `deterministic-only`

### Requirement: Per-Source Failure Visibility

When a configured source fails to fetch or returns zero items, `collect`
MUST surface that as a visible warning to the operator (via configured
logging output that reaches the console), in addition to the existing
non-fatal exit-0 behavior; the run MUST NOT abort because of it.

#### Scenario: A failing source produces a visible warning

- GIVEN one of several configured sources fails to fetch
- WHEN `collect` runs
- THEN a warning identifying that source is visible in the operator's
  output, and the run exits 0 using items from the remaining sources

#### Scenario: A source returning nothing is distinguishable from a crash

- GIVEN a configured source fetches successfully but yields zero items
- WHEN `collect` runs
- THEN the summary or logged output identifies that source as having
  returned nothing, distinct from a fetch failure
