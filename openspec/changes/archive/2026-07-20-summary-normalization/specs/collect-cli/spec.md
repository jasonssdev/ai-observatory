# Delta for collect-cli

## MODIFIED Requirements

### Requirement: Config Wiring

`collect` MUST read `DATA_DIR`, `DB_PATH`, `RECORDS_DIR`, `SOURCES_PATH`,
`USER_AGENT`, `RECORD_WINDOW_DAYS`, and `SUMMARY_MAX_CHARS` from config,
honoring `AIOBS_*` env overrides, with hardcoded defaults when unset.
`RECORD_WINDOW_DAYS` MUST default to `7` and MUST fail-safe to `7` when the
env value is invalid (non-integer) or negative. `SUMMARY_MAX_CHARS` MUST
default to `500` and MUST fail-safe to `500` when the env value is invalid
(non-integer) or negative.
(Previously: only `RECORD_WINDOW_DAYS` was documented among numeric,
fail-safe config values; `SUMMARY_MAX_CHARS` did not exist.)

#### Scenario: Defaults apply when no env vars set

- GIVEN no `AIOBS_*` environment variables are set
- WHEN `collect` runs
- THEN it uses `./data`, `data/observatory.db`, `data/records`,
  `./sources.yaml`, a record window of 7 days, and a summary cap of 500
  characters

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
