# Delta for collect-cli

## MODIFIED Requirements

### Requirement: End-of-Run Summary
`collect` MUST emit an end-of-run summary via `typer.echo` reporting:
sources queried, sources that returned nothing or failed, items collected,
items remaining after dedup, items classified during this run split into
significant/set-aside counts, and the active filter mode (`hybrid` or
`deterministic-only`). Logging MUST be configured so third-party HTTP
client loggers (`httpx`, `httpcore`) are raised to `WARNING` or higher,
while the application's own `INFO`-level logging remains enabled; this
ensures the summary is not buried under per-request log noise.
(Previously: `logging.basicConfig(level=logging.INFO)` applied `INFO` to
the root logger uniformly, so every `httpx`/`httpcore` request line was
printed at the same visibility as the application's own logging and the
end-of-run summary.)

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

#### Scenario: Third-party HTTP loggers are suppressed
- GIVEN `collect` has configured its logging
- WHEN the effective level of the `httpx` and `httpcore` loggers is
  inspected
- THEN each is at `WARNING` or higher, so their `INFO`-level request logs
  do not reach the console

#### Scenario: Application logging remains visible alongside suppression
- GIVEN `collect` has configured its logging with third-party loggers
  raised to `WARNING`
- WHEN the effective level of the application's own logger
  (`ai_observatory` or a descendant) is inspected
- THEN it remains at `INFO` or more verbose, so app-level `INFO` messages,
  the end-of-run summary, and per-source failure warnings stay visible

### Requirement: Per-Source Failure Visibility
When a configured source fails to fetch or returns zero items, `collect`
MUST surface that as a visible warning to the operator (via configured
logging output that reaches the console), in addition to the existing
non-fatal exit-0 behavior; the run MUST NOT abort because of it. This
warning MUST remain visible even with third-party HTTP loggers suppressed
to `WARNING`, since only `httpx`/`httpcore` are raised — the application's
own warning-level (and INFO-level) logging is unaffected.

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
