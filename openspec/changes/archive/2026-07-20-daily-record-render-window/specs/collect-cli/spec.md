# Delta for collect-cli

## MODIFIED Requirements

### Requirement: Config Wiring
`collect` MUST read `DATA_DIR`, `DB_PATH`, `RECORDS_DIR`, `SOURCES_PATH`,
`USER_AGENT`, and `RECORD_WINDOW_DAYS` from config, honoring `AIOBS_*` env
overrides, with hardcoded defaults when unset. `RECORD_WINDOW_DAYS` MUST
default to `7` and MUST fail-safe to `7` when the env value is invalid
(non-integer) or negative.
(Previously: read `DATA_DIR`, `DB_PATH`, `RECORDS_DIR`, `SOURCES_PATH`, and
`USER_AGENT` only, with no window config.)

#### Scenario: Defaults apply when no env vars set
- GIVEN no `AIOBS_*` environment variables are set
- WHEN `collect` runs
- THEN it uses `./data`, `data/observatory.db`, `data/records`,
  `./sources.yaml`, and a record window of 7 days

#### Scenario: Env override takes effect
- GIVEN `AIOBS_DB_PATH` is set to a custom path
- WHEN `collect` runs
- THEN items are written to the overridden database path

#### Scenario: Invalid or negative window falls back to default
- GIVEN `AIOBS_RECORD_WINDOW_DAYS` is set to a non-integer or negative value
- WHEN `collect` runs
- THEN the record window falls back to 7 days and the run completes without
  error
