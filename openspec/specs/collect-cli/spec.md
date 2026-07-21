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
`USER_AGENT`, and `RECORD_WINDOW_DAYS` from config, honoring `AIOBS_*` env
overrides, with hardcoded defaults when unset. `RECORD_WINDOW_DAYS` MUST
default to `7` and MUST fail-safe to `7` when the env value is invalid
(non-integer) or negative.

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

### Requirement: Non-Fatal Run Completion
`collect` MUST exit 0 even when one or more sources fail; failures are logged,
not raised to the CLI level.

#### Scenario: One unreachable source among nine
- GIVEN one of nine configured sources is unreachable
- WHEN `collect` runs
- THEN it exits 0 and produces a record from the remaining reachable sources
