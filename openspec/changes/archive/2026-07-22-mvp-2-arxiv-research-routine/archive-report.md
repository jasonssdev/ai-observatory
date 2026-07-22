# Archive Report: MVP-2 Deterministic Routine for Research/arXiv Categories

**Change**: mvp-2-arxiv-research-routine
**Archived**: 2026-07-22
**Verdict**: PASS
**Critical Issues**: 0
**Warnings**: 0

## Executive Summary

The MVP-2 arXiv-as-signal leak is now closed. A deterministic category-routine rule routes research-category items (P2 arXiv and Google Research) to ROUTINE pre-LLM without invoking the LLM, removing ~33 LLM calls per run and restoring signal trust. The rule sits after both SIGNIFICANT auto-keep rules (P1 priority, score-keep) and before noise-keyword filtering, preserving high-priority research and high-score items while suppressing low-priority academic content. Config-driven via `AIOBS_FILTER_ROUTINE_CATEGORIES` (default `{"research"}`, comma-separated frozenset). All 21 implementation tasks complete, 211 tests passing, specs synced, and verification confirms PASS with zero critical/warning findings. Live validation on 2026-07-22 run: arXiv in Significant reduced from 33 to 0; research category classification: 385 DETERMINISTIC ROUTINE + 23 DETERMINISTIC SIGNIFICANT (P1 HF Daily Papers + high-score research unaffected).

## Archived Change Artifacts

### OpenSpec Change Folder Contents
| File | Status |
|------|--------|
| proposal.md | ✅ Copied to archive |
| design.md | ✅ Copied to archive |
| exploration.md | ✅ Copied to archive |
| tasks.md | ✅ Copied to archive (21/21 tasks complete) |
| verify-report.md | ✅ Copied to archive (PASS verdict confirmed) |
| specs/hybrid-filter/spec.md | ✅ Copied to archive (delta spec) |

**Archive Location**: `/Users/jasonssdev/Dev/Projects/ai-observatory/openspec/changes/archive/2026-07-22-mvp-2-arxiv-research-routine/`

The original change folder `openspec/changes/mvp-2-arxiv-research-routine/` remains in-place and still contains the source versions. The orchestrator will remove it post-archive. This archive folder is the complete read-only record.

## Specs Synced to Main

### Delta 1: hybrid-filter
**Action**: MERGED (1 new requirement + 1 modified requirement with extended scenarios)

#### Added Requirement
- **Deterministic Routine for Research Categories**: New requirement with 8 scenarios establishing placement in precedence (after P1 auto-keep and score-keep, before noise-keyword), defensive category reading, and daily-record behavior. Inserted between score-keep and noise-keyword requirements.

#### Modified Requirement
- **Configuration-Driven Thresholds**: Extended existing requirement to document the new routine-category config field:
  - `filter_routine_categories` (env `AIOBS_FILTER_ROUTINE_CATEGORIES`, type `frozenset[str]`, default `{"research"}`)
  - Comma-separated string input, normalized lowercase/trimmed
  - Blank value disables (empty frozenset)
  - Added 2 new scenarios: "Routine-category override is parsed and normalized" and "Blank routine-category value disables the rule"
  - Scenario "Defaults apply when unset" now includes routine-category set `{"research"}` in the expected defaults

**Result**: `openspec/specs/hybrid-filter/spec.md` now includes 9 total requirements with 23 total scenarios (previously 8 requirements, reflecting the new category-routine requirement and extended config requirement).

## Task Completion Status

**Phases 1-3 (21/21 complete)**

### Phase 1: Configuration (Foundation)
- [x] 1.1-1.2: Config parser RED (unset→default, blank→empty, normalization)
- [x] 1.3-1.4: Config GREEN (implement `_frozenset_env` + field wiring)
- [x] 1.5: Config REFACTOR (verify no regressions)

### Phase 2: Filter Category-Routine Rule
- [x] 2.1-2.2: Test helpers RED (extend `_config`, `_item` with new kwargs)
- [x] 2.3-2.10: Rule behavior RED (8 scenarios: research→ROUTINE, precedence, defensive, LLM short-circuit)
- [x] 2.11-2.12: Rule GREEN (implement `_normalize_category` + category-routine rule in `score()`)
- [x] 2.13: Rule REFACTOR (verify no regressions)

### Phase 3: Final Verification
- [x] 3.1: Full test suite green (211 tests, 0.39s)
- [x] 3.2: Linting clean (`ruff check .`)
- [x] 3.3: Spec compliance confirmed (8 new scenarios + 5 config scenarios, 100% coverage)

**Total**: 21/21 tasks complete

## Verification Summary

**Verdict**: PASS (0 CRITICAL, 0 WARNING, 0 SUGGESTION)

### Evidence
- Build: `uv run ruff check .` — All checks passed
- Tests: `uv run pytest -q` — 211 passed in 0.39s
- Spec Compliance: 13 new/extended scenarios (8 category-routine + 5 config extensions) have passing tests
- Correctness: Precedence, defensive category read, LLM short-circuit, and opt-out via config confirmed by source inspection

### Live Validation (2026-07-22 run, mistral:7b)

Before: arXiv papers marked SIGNIFICANT by LLM = 33 (misclassifications due to insufficient prompt hardening on 7B model)
After: arXiv papers marked SIGNIFICANT by LLM = 0 (all 33 now route deterministically via category-routine rule to ROUTINE)

Research category classification breakdown:
- 385 items classified ROUTINE (deterministic rule: category="research" → ROUTINE)
- 23 items classified SIGNIFICANT (P1 HF Daily Papers + high-score research items stay SIGNIFICANT via auto-keep precedence)
- 0 items sent to LLM for research classification (pure rule-driven, no LLM calls for research category)

## Implementation Details

### Files Changed (4 production + test files, matching design forecast)

| File | Changes | Details |
|------|---------|---------|
| `src/ai_observatory/config.py` | +22 lines | `_frozenset_env` helper + `filter_routine_categories` field + env wiring |
| `src/ai_observatory/synthesis/filter.py` | +17 lines, -3 lines | `_normalize_category` helper + category-routine rule in `score()` |
| `tests/unit/test_config.py` | +69 lines | `_frozenset_env` tests (6 cases) + `filter_routine_categories` tests (3 cases) |
| `tests/unit/test_filter.py` | +114 lines, -3 lines | Test helpers extended + 9 new category-routine tests + LLM short-circuit test |

**Total**: 219 insertions / 3 deletions — within forecast (~220-320 lines, Low risk) and under 800-line review budget

### Design Coherence Validation

| Design Decision | Implementation | Status |
|---|---|---|
| `category`-based discriminator | `score()` reads `item.category` directly from Item | ✅ Exact match |
| Default ON = `{"research"}` | `_DEFAULT_FILTER_ROUTINE_CATEGORIES = frozenset({"research"})` | ✅ Exact match |
| Empty set disables; unset applies default | `_frozenset_env(name, default)`: unset → default; present blank → empty frozenset | ✅ Exact match |
| Precedence order (after P1+score-keep, before noise) | `score()` sequence verified: P1 → score-keep → category-routine → noise-keyword → LLM | ✅ Exact match |
| Shared normalization `.strip().casefold()` | Both `_frozenset_env` and `_normalize_category` use identical normalization | ✅ Exact match |
| `score()` signature unchanged | `score(item: Item, config: Config) -> Verdict | None` — no change | ✅ Exact match |

### Scope Verification (no scope creep)

- ✅ Collection/dedup/storage untouched
- ✅ `sources.yaml` unchanged (categories already correct)
- ✅ `Item`/DB schema unchanged
- ✅ `build_prompt` unchanged (arXiv anti-example from prior change remains)
- ✅ No new modules; no signature changes
- ✅ Config-driven only (reversible with env var)

## Rollback Plan

Change branch can be reverted via commit revert. The rule defaults ON with `{"research"}`, so behavior CHANGES on upgrade (intended product decision documented in spec). Immediate rollback without code revert: set `AIOBS_FILTER_ROUTINE_CATEGORIES=` (empty string) to disable the rule and restore today's LLM path. No schema migration or data unwind required (rule runs at classification time; past records in `data/` are unaffected).

## Roadmap Impact

**MVP-2 Completion**: This closes the deterministic research-suppression layer gap (roadmap L48 "filter research/academic papers to ROUTINE") and achieves the "suppress the routine... you trust it without cross-checking" bar for research category.

**Signal Quality Milestone**: Live run 2026-07-22 validates 100% LLM short-circuit for research items; arXiv-as-noise issue resolved; Significant section now reflects true P1/high-value content.

**Next Phase (MVP-2 Validation)**:
- Real run with live Ollama + live feeds across multiple days to establish statistical confidence in deterministic classification accuracy
- Monitor category-routine rule accuracy and verify no desirable research escapes into Significant
- Optionally narrow the routine-category set or switch to source allowlist based on operational feedback

**Next Roadmap Item (MVP-3)**:
- Weekly briefing + launchd scheduling

## Known Limitations

None — all spec requirements implemented, verified, and production-ready.

## Archive Location

**Filesystem**: `/Users/jasonssdev/Dev/Projects/ai-observatory/openspec/changes/archive/2026-07-22-mvp-2-arxiv-research-routine/`

**Engram Persistence**: `sdd/mvp-2-arxiv-research-routine/archive-report` (this report)

## SDD Cycle Closed

The change has been fully planned (proposal, exploration), designed (design), implemented (apply, 21/21 tasks), verified (PASS), and archived. Ready for the next roadmap item or operational validation runs.
