# Archive Report: MVP-2 Deterministic Score-Keep Signal Rule

**Change**: mvp-2-filter-score-signal
**Archived**: 2026-07-21
**Verdict**: PASS
**Critical Issues**: 0
**Warnings**: 0

## Executive Summary

The MVP-2 score-signal gap is now closed. A deterministic score-keep rule (third tier in the hybrid filter) reads normalized popularity signals from HF upvotes and HN points, auto-keeps high-scoring items SIGNIFICANT without LLM calls, and opt-in thresholds default disabled for zero out-of-the-box behavior change. All 28 implementation and refactor tasks complete (23 original + 5 post-verify pure refactor), 177 tests passing, specs synced, and verification confirms PASS with zero critical/warning findings. The shared-constants SUGGESTION from verify was proactively addressed by a post-verify refactor increment extracting signal-key literals into module-level constants and an enum.

## Archived Change Artifacts

### SDD Artifacts (Engram Observation IDs)
| Artifact | ID | Type | Status |
|----------|----|----|--------|
| Proposal | 1476 | architecture | Complete |
| Spec | 1477 | architecture | Complete |
| Design | 1478 | architecture | Complete |
| Tasks | 1479 | architecture | Complete (28/28) |
| Apply-Progress | 1480 | architecture | Complete |
| Verify-Report | 1481 | architecture | PASS |

### OpenSpec Change Folder Contents
| File | Status |
|------|--------|
| proposal.md | ✅ Copied to archive |
| design.md | ✅ Copied to archive |
| exploration.md | ✅ Copied to archive |
| tasks.md | ✅ Copied to archive (updated with Phase 6 refactor) |
| verify-report.md | ✅ Copied to archive (PASS verdict noted) |
| specs/hybrid-filter/spec.md | ✅ Copied to archive |
| specs/json-collection/spec.md | ✅ Copied to archive |

**Note**: The original change folder `openspec/changes/mvp-2-filter-score-signal/` remains in-place and still contains the source versions. The orchestrator will remove it post-archive. This archive folder `openspec/changes/archive/2026-07-21-mvp-2-filter-score-signal/` is the complete read-only record.

## Specs Synced to Main

### Delta 1: hybrid-filter
**Action**: MERGED (2 modifications to existing spec)

#### Added Requirements
- **Deterministic Auto-Keep for High-Score Items**: New requirement with 7 scenarios covering score-keep rule precedence, defensiveness, and per-source independence. Inserted after P1 auto-keep requirement to establish placement in the precedence order.

#### Modified Requirements
- **Configuration-Driven Thresholds**: Extended existing requirement to document two new optional score-keep thresholds:
  - `filter_hf_keep_upvotes` (env `AIOBS_FILTER_HF_KEEP_UPVOTES`, default `None`)
  - `filter_hn_keep_points` (env `AIOBS_FILTER_HN_KEEP_POINTS`, default `None`)
  - Added scenario: "Invalid score-keep override falls back to disabled"

**Result**: `openspec/specs/hybrid-filter/spec.md` now includes 8 total requirements (originally 6 + new 1 + modified 1 now showing 8 in the merged spec due to structure).

### Delta 2: json-collection
**Action**: MERGED (2 modifications to existing spec)

#### Modified Requirements
1. **HF Daily Papers Parsing**: Extended requirement to specify normalized signal keys in raw:
   - Adds `raw["signal_score"]` (int = paper.upvotes)
   - Adds `raw["signal_scale"] = "hf_upvotes"`
   - Scenario adjusted to expect these keys

2. **HN Algolia Parsing**: Extended requirement to specify normalized signal keys in raw:
   - Adds `raw["signal_score"]` (int = hits[].points)
   - Adds `raw["signal_scale"] = "hn_points"`
   - Scenario adjusted to expect these keys alongside existing URL/permalink contract

**Result**: `openspec/specs/json-collection/spec.md` now documents the additive normalization contract for both JSON collectors.

## Task Completion Status

- **Original Tasks (Phases 1-5)**: 23/23 complete, all marked [x]
- **Phase 6 Post-Verify Refactor**: 5/5 complete, all marked [x]
  - 6.1: `storage/models.py` — constants/enum extraction
  - 6.2: `collection/hf_papers.py` — constants adoption
  - 6.3: `collection/hn_algolia.py` — constants adoption
  - 6.4: `synthesis/filter.py` — constants/enum adoption
  - 6.5: Verification (177 tests before/after confirm zero behavior change)

**Total**: 28/28 tasks complete

## Verification Summary

**Verdict**: PASS (0 CRITICAL, 0 WARNING, 1 SUGGESTION ADDRESSED)

### Evidence
- Build: `uv run ruff check .` — All checks passed
- Tests: `uv run pytest -q` — 177 passed (baseline 155, +22 new)
- Spec Compliance: 20/20 scenarios have passing tests
- Correctness: Precedence, defensive read, and opt-in defaults confirmed by source inspection

### Addressed Suggestion
**Original Finding**: Extract shared string literals (`"signal_score"`, `"signal_scale"`, `"hf_upvotes"`, `"hn_points"`) as named constants to prevent future typo/scale mismatches.

**Action Taken (Phase 6 post-verify refactor)**:
- Added module-level constants to `storage/models.py`:
  - `SIGNAL_SCORE_KEY = "signal_score"`
  - `SIGNAL_SCALE_KEY = "signal_scale"`
  - `class SignalScale(StrEnum)` with `HF_UPVOTES = "hf_upvotes"` and `HN_POINTS = "hn_points"`
- Updated all references in `collection/hf_papers.py`, `collection/hn_algolia.py`, and `synthesis/filter.py` to use the constants/enum
- Verified: 177 tests confirm zero behavior change (pure refactor)

### Remaining Informational Notes
- **Coverage Tool**: Not configured in this project; scenario-to-test mapping serves as compliance evidence (runtime, not just static)
- **Opt-in Thresholds**: Both `filter_hf_keep_upvotes` and `filter_hn_keep_points` default to `None` (disabled). Starter values (HF ~50 / HN ~200) documented in prose only — not enforced defaults. Out-of-the-box behavior identical to today until an operator opts in.

## Known Deferred Limitations

None — all spec requirements implemented and verified.

## Roadmap Impact

**MVP-2 Completion**: This closes the deterministic score-signal layer gap (roadmap L42 "source priority + keyword/score thresholds").

**Next Phase (MVP-2 Validation)**:
- Real run with live Ollama + live feeds to establish tuning thresholds and validate end-to-end behavior (roadmap "Done when" criteria)
- Monitor score-keep rule accuracy and refine thresholds based on results

**Next Roadmap Item (MVP-3)**:
- Weekly briefing + launchd scheduling

## Rollback Plan

Change branch can be reverted via commit revert (commit hash `b4bad05`). Both thresholds default `None`, so the score-keep rule never fires out-of-the-box, and behavior remains identical to today even without revert. No schema migration or data unwind required.

## Archive Location

**Filesystem**: `/Users/jasonssdev/Dev/Projects/ai-observatory/openspec/changes/archive/2026-07-21-mvp-2-filter-score-signal/`

**Engram Persistence**: `sdd/mvp-2-filter-score-signal/archive-report` (this report)

## SDD Cycle Closed

The change has been fully planned (proposal), designed (design, exploration), implemented (apply, 28/28 tasks), verified (PASS), and archived. Ready for the next roadmap item.
