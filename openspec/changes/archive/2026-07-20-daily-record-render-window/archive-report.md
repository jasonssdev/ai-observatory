# Archive Report: daily-record-render-window

**Archive Date**: 2026-07-20  
**Change**: daily-record-render-window  
**Mode**: hybrid (Engram + OpenSpec filesystem)  
**Status**: Complete

## Artifact Traceability

All source artifacts are recorded by Engram observation ID for full traceability:

| Artifact | Type | Engram ID | Purpose |
|----------|------|-----------|---------|
| Proposal | architecture | 1365 | Original intent, scope, and approach |
| Spec Deltas | architecture | 1367 | Modified requirements for daily-record and collect-cli |
| Design | architecture | 1368 | Technical decisions, architecture, data flow |
| Tasks | architecture | 1370 | Implementation plan, all 11/11 marked complete |
| Verify Report | architecture | 1374 | Verification evidence, test results, spec compliance |

## What Shipped

### Implementation Summary
The change bounds daily-record rendering to a recent time window while keeping ingestion unbounded:

- **New Config Field**: `AIOBS_RECORD_WINDOW_DAYS` (int, default 7, fail-safe fallback for invalid/negative values)
- **Pure Helper**: `dates_within_window(candidate_dates, today, window_days)` in `storage/records.py` — deterministic, unit-testable, zero clock patching
- **CLI Wiring**: `collect()` computes `today` once at the edge; delegates windowed render loop via `_write_daily_records` seam
- **Test Coverage**: 13 new tests across config, records helper, and integration; all 62 tests passing
- **Code Quality**: `ruff check .` passes; no violations

### Task Completion
All 11/11 implementation tasks marked complete:
- [x] Phase 1: Config foundation (3 tasks)
- [x] Phase 2: Pure window helper (2 tasks)
- [x] Phase 3: CLI integration seam (3 tasks)
- [x] Phase 4: Spec alignment & verification (3 tasks)

### Verification Evidence
- `uv run pytest -q` → 62 passed in 0.07s (exit 0)
- `uv run ruff check .` → All checks passed (exit 0)
- All 7 spec scenarios covered by real, passing, runtime-exercised tests
- Design coherence confirmed: pure helper, fail-safe parsing, single untestable boundary

## Main Specs Merged

Two main specifications were updated to reflect the new behavior:

### 1. openspec/specs/daily-record/spec.md
**Modified Requirement**: "Full Regeneration from DB (Idempotency)"

**Changes**:
- Added window bound: `AIOBS_RECORD_WINDOW_DAYS` days of the run's UTC date + run date itself
- Added unbounded-DB guarantee: ingestion remains fully unbounded; only .md file set is bounded
- Added 3 new scenarios:
  - "Cold-start backlog stays bounded" — old items outside window excluded from .md generation
  - "Window of zero renders only today" — explicit zero-window behavior
  - "Run date is always rendered" — today's file always generated, even with no items

**Preserved**: All other requirements (Markdown Record Generation, Category Grouping, Item Line Format) unchanged.

### 2. openspec/specs/collect-cli/spec.md
**Modified Requirement**: "Config Wiring"

**Changes**:
- Added `RECORD_WINDOW_DAYS` to config read list: `DATA_DIR`, `DB_PATH`, `RECORDS_DIR`, `SOURCES_PATH`, `USER_AGENT`, **`RECORD_WINDOW_DAYS`**
- Added fail-safe parsing: default 7; invalid/negative → 7; zero → 0 (valid)
- Added scenario: "Invalid or negative window falls back to default" — explicit error handling

**Preserved**: All other requirements (Collect Command, Entry-Point Preservation, Non-Fatal Run Completion) unchanged.

## Out-of-Scope Items (Intentional Deferral)

The following items are explicitly noted as future work:

1. **655 Pre-existing Historical `.md` Files Cleanup**: These out-of-window files are left untouched by this change. Deletion is a separate future change (removal from `data/records/` directory). This was intentional per design's Migration/Rollout section — cleanup is out of scope for this window-bounding change.

## Archive Contents

✅ All artifacts present in `openspec/changes/archive/2026-07-20-daily-record-render-window/`:
- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/daily-record/spec.md` (delta)
- `specs/collect-cli/spec.md` (delta)
- `archive-report.md` (this file)

## Verification: PASS WITH WARNINGS

### CRITICAL Issues
0 — no critical blockers

### WARNINGS
1 — Out-of-scope uncommitted changes in working tree:
- `.gitignore` (unrelated .gitignore changes)
- `src/ai_observatory/collection/rss.py` (follow_redirects fix)
- `src/ai_observatory/storage/db.py` (parent-dir creation)
- `tests/integration/test_db.py`, `tests/unit/test_rss.py` (tests for above)

**Status**: These changes are unrelated to the daily-record-render-window specification, design, and tasks. They must be committed separately with their own message before or at the same time, but NOT bundled into this change's PR. This is a delivery/commit concern, NOT a spec-compliance defect. Per orchestrator context: not a blocking issue.

### SUGGESTIONS
0

## SDD Cycle Complete

✅ The change has been fully planned (proposal), specified (specs), designed (design), implemented (all tasks), verified (all tests passing), and archived. The source of truth (`openspec/specs/`) has been updated and is ready for the next change.

### Ready for Delivery
- Code implementation complete and passing all tests
- Specs merged into main source of truth
- Change folder archived with full audit trail
- Review receipt required for commit (per native gentle-ai review lifecycle)
- Note: Separate the unrelated rss.py/db.py changes before committing this change

## Deferred / Future Changes
- **Cleanup 655 historical .md files**: scheduled as a separate change after this one stabilizes
