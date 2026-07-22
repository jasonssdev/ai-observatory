# collect-cli Specification

## Purpose

Expose the fetch → parse → dedup → store → render pipeline as a single
`collect` command, preserving the existing package entry-point contract.

## Requirements

### Requirement: Collect Command
The system MUST expose a `collect` command (typer) that runs the full
pipeline for all configured sources.

#### Scenario: Successful run produces a record
- GIVEN a valid `sources.yaml` and reachable feeds
- WHEN `ai-observatory collect` runs
- THEN it exits 0 and `data/records/<today>.md` is created or updated

### Requirement: Entry-Point Preservation
The `ai_observatory:main` console-script entry point MUST remain valid;
`main()` MUST invoke the typer app without breaking the existing
`ai-observatory` executable contract.

#### Scenario: Installed script still resolves
- GIVEN the package installed with its `[project.scripts]` entry point
- WHEN `ai-observatory collect` is invoked as the installed executable
- THEN `main()` dispatches to the typer app and the `collect` command runs

### Requirement: Config Wiring
`collect` MUST read `DATA_DIR`, `DB_PATH`, `RECORDS_DIR`, `SOURCES_PATH`,
`USER_AGENT`, `RECORD_WINDOW_DAYS`, `SUMMARY_MAX_CHARS`,
`AIOBS_HF_MIN_UPVOTES`, and `AIOBS_HN_MIN_POINTS` from config, honoring
`AIOBS_*` env overrides, with hardcoded defaults when unset.
`RECORD_WINDOW_DAYS` MUST default to `7` and MUST fail-safe to `7` when the
env value is invalid (non-integer) or negative. `SUMMARY_MAX_CHARS` MUST
default to `500` and MUST fail-safe to `500` when the env value is invalid
(non-integer) or negative. `AIOBS_HF_MIN_UPVOTES` MUST default to `5` and
`AIOBS_HN_MIN_POINTS` MUST default to `30`; both MUST fail-safe to their
default when the env value is invalid (non-integer) or negative.
(Previously: only `RECORD_WINDOW_DAYS` was documented among numeric,
fail-safe config values; `SUMMARY_MAX_CHARS` did not exist; `AIOBS_HF_MIN_UPVOTES` and `AIOBS_HN_MIN_POINTS` did not exist.)

#### Scenario: Defaults apply when no env vars set
- GIVEN no `AIOBS_*` environment variables are set
- WHEN `collect` runs
- THEN it uses `./data`, `data/observatory.db`, `data/records`,
  `./sources.yaml`, a record window of 7 days, a summary cap of 500
  characters, an HF minimum-upvotes cutoff of 5, and an HN minimum-points
  cutoff of 30

#### Scenario: Env override takes effect
- GIVEN `AIOBS_DB_PATH` is set to a custom path
- WHEN `collect` runs
- THEN items are written to the overridden database path

#### Scenario: Invalid or negative window falls back to default
- GIVEN `AIOBS_RECORD_WINDOW_DAYS` is set to a non-integer or negative value
- WHEN `collect` runs
- THEN the record window falls back to 7 days and the run completes without
  error

#### Scenario: Invalid or negative summary cap falls back to default
- GIVEN `AIOBS_SUMMARY_MAX_CHARS` is set to a non-integer or negative value
- WHEN `collect` runs
- THEN the summary cap falls back to 500 characters and the run completes
  without error

#### Scenario: Invalid or negative JSON thresholds fall back to defaults
- GIVEN `AIOBS_HF_MIN_UPVOTES` or `AIOBS_HN_MIN_POINTS` is set to a
  non-integer or negative value
- WHEN `collect` runs
- THEN the corresponding threshold falls back to its documented default and
  the run completes without error

### Requirement: Collector Dispatch by Source
`collect` MUST route each configured source to the collector matching its
`source.collector` value (`rss` → `RssCollector`, `hf_papers` →
`HfPapersCollector`, `hn_algolia` → `HnAlgoliaCollector`). A source whose
`collector` value matches none of the known collectors MUST be logged and
skipped, and MUST NOT abort the run.

#### Scenario: Each source routes to its matching collector
- GIVEN a `sources.yaml` with `rss`, `hf_papers`, and `hn_algolia` sources
- WHEN `collect` runs
- THEN each source's items are produced by the collector matching its
  `collector` value

#### Scenario: Unknown collector value is skipped, not fatal
- GIVEN a source whose `collector` value has no matching collector
- WHEN `collect` runs
- THEN that source is logged and skipped, and the run exits 0 with items
  from the remaining sources

#### Scenario: P2 RSS feeds flow through the existing RSS collector
- GIVEN a `sources.yaml` with `priority: 2` entries whose `collector` is `rss`
- WHEN `collect` runs
- THEN those sources are collected via `RssCollector` identically to
  priority-1 RSS sources

### Requirement: Source Loading Includes All Collector Types
`load_sources` MUST return every valid entry from `sources.yaml` regardless
of its `collector` value, keeping only the existing per-entry malformed-key
skip. Dispatch to the correct collector (or skip on an unknown value) is the
CLI's responsibility, not the loader's.
(Previously: `load_sources` hard-filtered its return value to entries where
`collector == "rss"`, silently dropping all non-RSS sources.)

#### Scenario: Non-RSS sources are returned
- GIVEN a `sources.yaml` with `rss`, `hf_papers`, and `hn_algolia` entries
- WHEN `load_sources` loads the file
- THEN all three entries are present in the returned list

#### Scenario: Malformed entry is still skipped
- GIVEN a `sources.yaml` entry missing a required key
- WHEN `load_sources` loads the file
- THEN that entry is logged and skipped, and all other valid entries load
  regardless of their `collector` value

### Requirement: Non-Fatal Run Completion
`collect` MUST exit 0 even when one or more sources fail; failures are logged,
not raised to the CLI level.

#### Scenario: One unreachable source among nine
- GIVEN one of nine configured sources is unreachable
- WHEN `collect` runs
- THEN it exits 0 and produces a record from the remaining reachable sources

### Requirement: End-of-Run Summary
`collect` MUST emit an end-of-run summary via `typer.echo` reporting:
sources queried, sources that returned nothing or failed, items collected,
items remaining after dedup, items classified during this run split into
significant/set-aside counts, and the active filter mode (`hybrid` or
`deterministic-only`). Logging MUST be configured so third-party HTTP
client loggers (`httpx`, `httpcore`) are raised to `WARNING` or higher,
while the application's own `INFO`-level logging remains enabled; this
ensures the summary is not buried under per-request log noise.

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

### Requirement: Live Progress Feedback
`collect` MUST display live progress feedback during both the source-collection phase (as sources are being fetched) and the LLM-classification phase (as items are being classified). Progress feedback is rendered via `typer.progressbar` and MUST degrade gracefully in non-TTY contexts (the bars are silent when stdout is not a terminal).

#### Scenario: Collection phase displays source name
- GIVEN `collect` is run in a terminal with reachable feeds
- WHEN the source-collection phase executes
- THEN a progress bar labeled "Collecting" displays, showing the current source being fetched by name

#### Scenario: Classification phase shows item count
- GIVEN items have been collected and deduplicated
- WHEN the classification phase executes
- THEN a progress bar labeled "Classifying" displays, advancing once per item classified (deterministic or LLM)

#### Scenario: Progress degrades gracefully in non-TTY
- GIVEN `collect` is invoked with stdout redirected to a file or pipe (non-TTY)
- WHEN `collect` runs
- THEN the progress bars are silent; the end-of-run summary, per-source warnings, and logging remain visible

#### Scenario: Behavior unchanged when progress is not rendered
- GIVEN the progress bars do not render (non-TTY, or testing environments where progress is disabled)
- WHEN `collect` runs
- THEN the collected/deduped/classified item counts, verdicts, and all other behavior remain identical to runs where progress bars are visible
