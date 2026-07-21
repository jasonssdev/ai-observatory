# Archive Report: Summary Normalization

**Date**: 2026-07-20  
**Change**: summary-normalization  
**Status**: COMPLETE  
**Verdict**: PASS (0 CRITICAL, 0 WARNING, 0 SUGGESTION)

## Executive Summary

The `summary-normalization` change has been successfully implemented, verified, and archived. All 12 implementation tasks completed with 81/81 tests passing. Delta specs merged into main specs. Change archived to `openspec/changes/archive/2026-07-20-summary-normalization/`.

## Artifacts Archived

| Artifact | Status | Observation ID |
|----------|--------|-----------------|
| Proposal | Present | #1388 |
| Spec Deltas | Present | #1389 |
| Design | Present | #1390 |
| Tasks (12/12 complete) | Present | #1391 |
| Verify Report (PASS) | Present | #1394 |
| Archive Report | Present | This document |

## Specification Merge Summary

### Feed Collection Specification
**Status**: MERGED  
**Path**: `openspec/specs/feed-collection/spec.md`

**Changes**:
- Updated "Feed Parsing" requirement to specify normalized summaries
- Requirement now mandates: HTML tags removed, entities unescaped, first paragraph only, truncated to AIOBS_SUMMARY_MAX_CHARS with ellipsis
- Added 6 new scenarios:
  - HTML entry normalizes to plain text
  - Trailing metadata block is dropped
  - Long multi-paragraph body is truncated
  - Entry with no description yields empty summary
  - Zero max_chars yields empty summary
  - (Plus 2 existing scenarios preserved: Well-formed feed parses, Malformed feed yields no entries)

### Collect CLI Specification
**Status**: MERGED  
**Path**: `openspec/specs/collect-cli/spec.md`

**Changes**:
- Updated "Config Wiring" requirement to add AIOBS_SUMMARY_MAX_CHARS
- Requirement now includes both RECORD_WINDOW_DAYS and SUMMARY_MAX_CHARS with same fail-safe pattern (default 500, invalid/negative → 500)
- Updated "Defaults apply when no env vars set" scenario to include summary cap of 500
- Added new scenario: "Invalid or negative summary cap falls back to default"

### Daily Record Specification
**Status**: MERGED  
**Path**: `openspec/specs/daily-record/spec.md`

**Changes**:
- Updated "Item Line Format" requirement with clarification that rendered summary is the normalized plain-text value from feed parsing
- Change is documentary only (no behavior change; render format unchanged)
- Existing scenario preserved

## Implementation Summary

**Total Tasks**: 12  
**Completed**: 12/12  
**Test Suite**: 81 passed (62 baseline + 19 new)  
**Lint**: All checks passed (ruff)

### Work Unit 1: Config + normalize_summary + rss.py wiring

**Phases Completed**:
1. Phase 1 (Config): Config.summary_max_chars field added with _int_env pattern
2. Phase 2 (normalize_summary): Pure helper in new collection/text.py with 5-step algorithm
3. Phase 3 (Wire into rss.py): parse_feed signature updated, RssCollector threaded with max_chars
4. Phase 4 (Spec Alignment): daily-record clarification (no code change needed)
5. Phase 5 (Verification): Full test suite green, lint passed

### Files Changed Summary
- **New**: collection/text.py (normalize_summary + HTMLParser), test_text.py, 3 XML fixtures
- **Modified**: rss.py (call at :124, RssCollector threading), config.py (summary_max_chars field), cli.py (:56 production call site), test_rss.py, test_config.py, test_collect_integration.py

## Verification Results

**Schema**: gentle-ai.verify-result/v1  
**Verdict**: PASS  

**Completeness**:
- Tasks: 12/12 complete
- Requirements: 3/3 (feed-collection, collect-cli, daily-record)
- Scenarios: 12/12 passing

**Test Results**:
- Command: `uv run pytest -q`
- Exit code: 0
- Tests passed: 81/81
- Coverage:
  - test_config.py: 5 cases (default, override, invalid, negative, zero)
  - test_text.py: 10 cases (HTML, entity decode, first-paragraph, truncation, empty, max_chars edge cases)
  - test_rss.py: 4 new cases (fixtures: html_summary, empty_summary, long_summary, regression)
  - Integration: Constructor updated for all call sites

**Lint Results**:
- Command: `uv run ruff check .`
- Exit code: 0
- All checks passed

**Design Conformance**:
- Pure normalize_summary function: Implemented ✓
- 5-step algorithm with exact order: Implemented ✓
- Tolerant HTMLParser with convert_charrefs=True: Implemented ✓
- Explicit max_chars threading: Implemented ✓
- All 4 RssCollector call sites updated: Verified ✓
- raw field untouched: Confirmed ✓
- No schema/migration changes: Confirmed ✓

## Operational Notes

### Non-Retroactive Behavior
The change is non-retroactive. Existing dirty rows remain unchanged due to `INSERT OR IGNORE` deduplication by item ID. To reset:
```bash
rm -rf data/
# Then re-collect
```

### Config Behavior
- AIOBS_SUMMARY_MAX_CHARS defaults to 500
- Invalid or negative values fail-safe to 500
- Zero (0) is valid and yields empty summaries

### Migration
No migration required. Schema `summary TEXT NOT NULL` unchanged. Dedup/storage/render format unchanged. daily-record already omits empty summaries via existing `if item.summary:` check.

## Traceability

| SDD Artifact | Engram ID | Status |
|--------------|-----------|--------|
| Proposal | #1388 | Retrieved |
| Spec | #1389 | Retrieved |
| Design | #1390 | Retrieved |
| Tasks | #1391 | Retrieved |
| Verify Report | #1394 | Retrieved |
| Archive Report | (this document) | Created |

## Delivery Status

**Ready for**: git commit and PR to main  
**Merged into source of truth**: openspec/specs/ (3 specs updated)  
**Archived**: openspec/changes/archive/2026-07-20-summary-normalization/

## Summary

The summary-normalization change is production-ready. All implementation tasks complete, all tests passing, all specs merged, design conformance verified, and archive created. No blockers. No CRITICAL or WARNING findings. Ready to commit.
