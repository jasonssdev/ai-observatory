# Archive Report: MVP-1 Daily Record Collector

**Change**: mvp-1-daily-collector
**Archived**: 2026-07-20
**Verdict**: Fully implemented, verified PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 1 SUGGESTION), and archived.

## SDD Artifacts Archived

This archive contains the complete artifact trail for the MVP-1 Daily Record Collector change, closing the SDD cycle.

### Artifact Observation IDs (Engram traceability)

| Artifact | Topic Key | Observation ID | Status |
|----------|-----------|---|---|
| Proposal | sdd/mvp-1-daily-collector/proposal | 1313 | Complete |
| Spec | sdd/mvp-1-daily-collector/spec | 1322 | Complete |
| Design | sdd/mvp-1-daily-collector/design | 1320 | Complete |
| Tasks | sdd/mvp-1-daily-collector/tasks | 1324 | 36/36 complete |
| Verification Report | sdd/mvp-1-daily-collector/verify-report | 1331 | PASS WITH WARNINGS |
| Apply Progress | sdd/mvp-1-daily-collector/apply-progress | 1329 | Complete (internal reference) |

### Archived Contents

- `proposal.md` — Intent, scope, capabilities, approach, and 9 key decisions
- `design.md` — Technical architecture, decisions, data flow, file changes, interfaces
- `exploration.md` — Early scope investigation, approaches considered, recommendations
- `tasks.md` — 36 implementation tasks across 6 phases (all checked)
- `verify-report.md` — Full verification with 42/42 tests passing, 0 CRITICAL issues
- `specs/` — 5 new capability specifications (feed-collection, item-deduplication, item-storage, daily-record, collect-cli)

## Specifications Synced to Main Specs

Five new capabilities were defined and are now archived as the source of truth. All delta specs are full specs (no prior main specs existed).

### Synced to `openspec/specs/`

| Domain | Status | Details |
|--------|--------|---------|
| feed-collection | Created | Fetch RSS/Atom over HTTP, parse into normalized entries, isolate per-source failures |
| item-deduplication | Created | Stable persistent id from canonical URL, in-run title-hash collision resolution |
| item-storage | Created | SQLite `items` table as source of truth, idempotent upsert, query-by-date |
| daily-record | Created | Fully-regenerated Markdown record per UTC calendar day, grouped by category/priority |
| collect-cli | Created | Single `collect` command pipeline, config wiring, entry-point preservation |

**Note**: No existing main specs required merging — all 5 are new capabilities added by this change.

## Verification Summary

**Verdict**: PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 1 SUGGESTION)

- **Test Suite**: 42/42 passing (`uv run pytest -q`)
- **Lint**: All checks passed (`uv run ruff check .`)
- **Tasks**: 36/36 implementation tasks checked
- **Entry Point**: `ai-observatory --help` resolved via `ai_observatory:main` → typer app
- **Critical Issues**: 0 (prior CRITICAL resolved before archive)

### Non-Blocking Findings

**WARNINGs:**
1. `priority` vs `source_priority` naming drift between spec prose and implementation — informational only, no functional risk
2. `main()` wiring deviation from design's exact import form — functionally identical, done for testability

**SUGGESTION:**
1. TZ-aware vs. naive `published_at` normalization branch coverage is implicit via feedparser; explicit per-branch test would be a future improvement

All findings are non-blocking and do not prevent archive.

## Known Deferred Limitations

The following limitations are intentionally deferred to future releases and are recorded here for visibility:

| Limitation | Target | Notes |
|-----------|--------|-------|
| Cross-run title-hash dedup | MVP-2 | In-run title-hash collision resolution works; cross-run title dedup (e.g., same story retold later under a different URL/title) is a future enhancement. MVP-1 relies on canonical URL identity for cross-run dedup. |
| Structured logging + source health metrics | v1.0 | Per-source error logging exists (malformed feeds, timeouts); full source health dashboard and structured metrics are v1.0 scope. |
| Markdown link escaping | Deferred | Feed items with `]` or `[` in titles may render broken links in Markdown; proper escaping is a low-priority cleanup (no feeds in MVP-1 test suite exhibit this). |

## Spec Coverage

All 5 domains are fully implemented and test-covered:

- **feed-collection**: 7/8 scenarios test-covered (TZ normalization implicit via feedparser)
- **item-deduplication**: 6/6 scenarios PASS
- **item-storage**: 5/5 scenarios PASS (including canonical_url/title_hash persistence)
- **daily-record**: 5/5 scenarios PASS
- **collect-cli**: 5/5 scenarios PASS

Mandatory case coverage (success, malformed feed, duplicate item, idempotent re-run, missing date) all verified.

## Implementation Summary

**Scope**: 5 new capabilities (9 new modules + tests + sources.yaml)
**Size**: ~1564 insertions across 25 files
**Approach**: Strict TDD (httpx fetch → feedparser parse → pure dedup → sqlite store → Markdown render)
**Entry Point**: Preserved `ai_observatory:main` as typer app wrapper
**Dependencies**: No new runtime deps (stdlib sqlite3 + existing feedparser, httpx, pyyaml, typer)

## Rollback

This is a new feature slice with no existing behavior depending on it:
- Revert the feature branch
- Restore stub `main()`
- Delete `data/observatory.db` and `data/records/` (gitignored, safe to reset)
- No database migrations to unwind

## Next Steps

The MVP-1 Daily Record Collector is complete and closed. The next change should follow from the project roadmap (e.g., MVP-2 enhancements such as cross-run title dedup or structured logging).

---

**Archive prepared**: 2026-07-20
**SDD Cycle**: Complete
**Status**: Ready for production deployment after merge and release.
