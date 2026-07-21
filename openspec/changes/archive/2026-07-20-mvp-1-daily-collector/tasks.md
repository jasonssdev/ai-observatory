# Tasks: MVP-1 Daily Record Collector

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~900-1050 (9 new modules, tests+fixtures, sources.yaml) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 -> PR2 -> PR3 -> PR4 |
| Delivery strategy | auto-forecast (undefined value; treated as ask-on-risk) |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

**Apply-time delivery resolution**: single PR with `size:exception` explicitly
accepted by the maintainer (per apply invocation instructions). Chained-PR
recommendation superseded for this apply pass; actual diff ~1564 insertions
across 25 files (see apply-progress for exact stat).

### Suggested Work Units

| Unit | Goal | PR | Focused test | Runtime harness | Rollback boundary |
|------|------|----|--------------|------------------|--------------------|
| 1 | Models + pure dedup (`storage/models.py`, `collection/base.py`, `collection/dedup.py`) | PR1 | `pytest tests/unit/test_dedup.py -q` | N/A — pure, no I/O | Revert 3 files, unused elsewhere |
| 2 | Fetch/parse + sources loader (`collection/rss.py`, `collection/sources.py`, fixtures) | PR2 | `pytest tests/unit/test_rss.py tests/unit/test_sources.py -q` | `parse_feed` against fixture bytes | Revert 2 files+fixtures, unused until CLI |
| 3 | Storage + records (`storage/db.py`, `storage/records.py`) | PR3 | `pytest tests/integration/test_db.py tests/unit/test_records.py -q` | `:memory:` sqlite run | Revert 2 files, no CLI dependency yet |
| 4 | Config + CLI + entry point + `sources.yaml` | PR4 | `pytest tests/smoke/test_cli.py -q` | `ai-observatory collect` (CliRunner, mocked fetcher) | Revert wiring files; PR1-3 stay valid |

## Phase 1: Foundation

- [x] 1.1 `tests/fixtures/`: `feed_valid.xml`, `feed_malformed.xml`, `feed_missing_date.xml`
- [x] 1.2 `storage/models.py`: frozen `Item` dataclass
- [x] 1.3 `collection/base.py`: frozen `Source` dataclass + `Fetcher`/`Collector` Protocols
- [x] 1.4 `sources.yaml`: 9 feeds (8 P1 + Google AI P2)

## Phase 2: Dedup (`collection/dedup.py`, pure)

- [x] 2.1 RED `test_dedup.py::test_canonicalize_url` — tracking-param strip vs non-tracking kept, scheme/host/port/slash/fragment cases
- [x] 2.2 GREEN `canonicalize_url`
- [x] 2.3 RED `test_title_hash_and_item_id` — normalization + determinism
- [x] 2.4 GREEN `title_hash`, `item_id`
- [x] 2.5 RED `test_dedup_batch` — dup id, title-hash collision priority win, tie by `published_at`, tie by lexical id
- [x] 2.6 GREEN `dedup_batch`

## Phase 3: Feed Collection (`collection/rss.py`, `collection/sources.py`)

- [x] 3.1 RED `test_rss.py::test_parse_feed` — success, malformed (zero entries, no raise), missing-date (defaults to `collected_at`)
- [x] 3.2 GREEN `parse_feed(bytes) -> list[Item]`
- [x] 3.3 RED `test_httpx_fetcher` — `MockTransport` success + configured UA header assertion
- [x] 3.4 GREEN `HttpxFetcher`
- [x] 3.5 RED `test_rss_collector_isolation` — `MockTransport` raises -> log+skip, no raise
- [x] 3.6 GREEN `RssCollector(fetcher)`
- [x] 3.7 RED `test_sources.py::test_load_sources` — parses yaml, filters `collector=="rss"`
- [x] 3.8 GREEN `load_sources(path)`

## Phase 4: Storage (`storage/db.py`, `storage/records.py`)

- [x] 4.1 RED `test_db.py::test_schema` — `connect(":memory:")` creates table + indexes
- [x] 4.2 GREEN `connect` + schema DDL
- [x] 4.3 RED `test_upsert_items` — dup id -> one row; re-run unchanged -> zero new rows; `raw` is valid JSON
- [x] 4.4 GREEN `upsert_items` (`INSERT OR IGNORE`)
- [x] 4.5 RED `test_items_for_date` — returns only that UTC day's items
- [x] 4.6 GREEN `items_for_date`
- [x] 4.7 RED `test_records.py::test_render_markdown` — header count, category grouping, priority/time sort, line format
- [x] 4.8 GREEN `render_markdown(items, date)`
- [x] 4.9 RED `test_write_record` — full regen overwrites; re-run with 1 new item appears once alongside prior
- [x] 4.10 GREEN `write_record(path, content)`

## Phase 5: Config, CLI, Entry Point

- [x] 5.1 RED `test_config.py::test_config_defaults_and_overrides` — no env -> defaults; `AIOBS_DB_PATH` -> overridden
- [x] 5.2 GREEN `config.py`: frozen `Config` from `AIOBS_*` env + defaults
- [x] 5.3 RED `test_cli.py::test_collect` — CliRunner + mocked fetcher: success -> exit 0, record written; 1/9 unreachable -> exit 0, record from remaining 8
- [x] 5.4 GREEN `cli.py`: `app`, `collect` wiring config -> `load_sources` -> `RssCollector` -> `dedup_batch` -> `upsert_items` -> `write_record`
- [x] 5.5 RED `test_main_entrypoint` — `ai_observatory:main` invokes typer `app`
- [x] 5.6 GREEN rewire `__init__.py`: `main()` -> `from .cli import app; app()` (implemented as `from ai_observatory import cli` + `cli.app()`, see Deviations)

## Phase 6: Integration Verification

- [x] 6.1 Integration test: 2 mocked sources sharing a duplicate item -> single row, single record line
- [x] 6.2 Run `uv run pytest` and `uv run ruff check .` — all green

**Status**: 36/36 tasks complete. 41/41 tests passing. `ruff check .` clean.
See `sdd/mvp-1-daily-collector/apply-progress` (Engram) for full TDD evidence
and deviation notes.
