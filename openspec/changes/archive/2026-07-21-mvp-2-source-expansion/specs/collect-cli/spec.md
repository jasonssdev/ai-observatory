# Delta for collect-cli

## ADDED Requirements

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

## MODIFIED Requirements

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
(Previously: `RECORD_WINDOW_DAYS` and `SUMMARY_MAX_CHARS` were the only
documented numeric, fail-safe config values; `AIOBS_HF_MIN_UPVOTES` and
`AIOBS_HN_MIN_POINTS` did not exist.)

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
