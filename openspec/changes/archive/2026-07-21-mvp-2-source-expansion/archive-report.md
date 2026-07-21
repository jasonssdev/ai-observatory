# Archive Report: mvp-2-source-expansion

**Archived Date**: 2026-07-21
**Change Name**: mvp-2-source-expansion (MVP-2 slice 3/3)
**Branch**: feat/mvp-2-source-expansion (commit dbad240)
**Verdict**: PASS WITH WARNINGS (size:exception accepted)
**Status**: Complete and closed

## SDD Artifact Traceability

All change artifacts have been verified, archived, and persisted to Engram for future reference.

| Artifact | Type | Observation ID | Status |
|----------|------|---|--------|
| Proposal | architecture | #1463 | Archived |
| Spec (json-collection + collect-cli delta) | architecture | #1465 | Archived |
| Design | architecture | #1466 | Archived |
| Tasks | architecture | #1467 | Archived (34/34 complete) |
| Verify Report | architecture | #1469 | Archived |

## Specs Synced to Main

### New Capability: json-collection

**Source**: `openspec/changes/mvp-2-source-expansion/specs/json-collection/spec.md`
**Target**: `openspec/specs/json-collection/spec.md`
**Action**: Created (full NEW capability)

The json-collection specification defines two dedicated JSON-API collectors:
- **HF Daily Papers Parsing**: Normalize HF Daily Papers JSON, threshold by `paper.upvotes` (default 5)
- **HN Algolia Parsing**: Normalize HN Algolia JSON, threshold by `points` (default 30)
- **Score Threshold Before Storage**: Drop below-cutoff items before storage
- **Configuration-Driven Thresholds**: `AIOBS_HF_MIN_UPVOTES` and `AIOBS_HN_MIN_POINTS` via environment
- **Per-Source Failure Isolation**: Never-raise contract matching RssCollector
- **Dedup Compatibility**: Use canonical-URL + title-hash identity scheme matching RSS items

**Requirements**: 6 requirements, 18 scenarios — all passed in verification.

### Modified Capability: collect-cli

**Source**: `openspec/changes/mvp-2-source-expansion/specs/collect-cli/spec.md`
**Target**: `openspec/specs/collect-cli/spec.md`
**Action**: Merged (ADDED 2 requirements, MODIFIED 1 requirement)

**Changes merged**:
1. **ADDED Requirement: Collector Dispatch by Source** — Route sources to collectors by `source.collector` value; unknown collector logged and skipped, never fatal
2. **ADDED Requirement: Source Loading Includes All Collector Types** — `load_sources` returns all valid sources, not just `rss` filtered
3. **MODIFIED Requirement: Config Wiring** — Added `AIOBS_HF_MIN_UPVOTES` (default 5) and `AIOBS_HN_MIN_POINTS` (default 30) to existing config read requirement

All existing requirements (Collect Command, Entry-Point Preservation, Non-Fatal Run Completion) preserved unchanged.

## Archived Contents

Complete change folder structure archived at `openspec/changes/archive/2026-07-21-mvp-2-source-expansion/`:

- `proposal.md` ✓ — Change intent, scope, capabilities, key decisions (9), testing plan, risks, rollback
- `design.md` ✓ — Technical approach, architecture decisions (5), data flow, interfaces, file changes, testing strategy
- `tasks.md` ✓ — 34/34 tasks complete; 10 phases from config to final gates; review workload forecast (HIGH budget risk, size:exception accepted)
- `verify-report.md` ✓ — PASS WITH WARNINGS; all scenarios/tests passing; 155 pytest green; 1 WARNING + 1 SUGGESTION
- `exploration.md` ✓ — Background research, current state, grounded JSON shapes, affected areas, design approaches, open questions resolved
- `specs/json-collection/spec.md` ✓ — New 6-requirement capability (all passed)
- `specs/collect-cli/spec.md` ✓ — Delta with 2 ADDED + 1 MODIFIED requirement (all merged)

## Verification Summary

**Verdict**: PASS WITH WARNINGS

**Evidence**:
- All 34 tasks marked complete in tasks.md and confirmed in code
- `uv run pytest -q` → 155 passed, 0 failed, 0 skipped
- `uv run ruff check .` → All checks passed
- All json-collection spec scenarios covered by passing tests
- All collect-cli delta scenarios covered by passing tests
- Code-level verification: never-raise contract confirmed for both HF and HN collectors
- Canonical URL logic verified (HN external → fallback permalink; HF papers/{id})
- Config thresholds verified (defaults + env override + fail-safe)
- `load_sources` filter removal verified (no `== "rss"` filter remains)

## Known Issues

### WARNING (1): Review Workload Footprint
- **Issue**: Single-PR footprint exceeds orchestrator's 800-line override
- **Details**: ~891-939 authored lines (372 changed in tracked files + 498 in new files + 48 fixtures)
- **Impact**: Process/governance concern; tasks.md's original 2-PR chain forecast was explicitly superseded by orchestrator instruction
- **Resolution**: Known, directed tradeoff; surfaced for visibility before merge

### SUGGESTION (1): Mixed-Source Failure Integration Test
- **Issue**: No end-to-end integration test for "one JSON source unreachable while other sources (RSS + JSON) stay healthy in the same collect() run"
- **Details**: Contract proven at unit level (collector isolation tests + code inspection), but not exercised end-to-end
- **Impact**: Non-blocking; existing coverage is sufficient for correctness
- **Resolution**: Recommended as follow-up; not required for MVP-2 closure

## Known Deferred Limitations

These are OUT of scope for MVP-2; scheduled for future slices:

| Limitation | Target | Reason |
|-----------|--------|--------|
| Bridged/RSSHub sources | v1.0 | Requires API abstraction; low priority |
| Apify/X sources | v1.0 | Requires platform-specific clients; v1.0 scope |
| Weekly briefing synthesis | MVP-3 | Depends on LLM score ranking; scheduling dependent |
| Synthesize CLI | MVP-3 | High-level feature; follows scoring |
| Launchd scheduling | MVP-3 | Platform-specific; after briefing completion |
| Item.score column | Deferred | Score lives in `raw` JSON; migration-free for now; future hybrid-filter enhancement can read from raw |
| Mixed-source-failure integration test | Follow-up | Suggested non-critical test; contract proven at unit level |
| Threshold defaults tuning | Post-launch | HF upvotes=5, HN points=30 need real-world validation after live run |

## Rollback Plan

Additive slice. To rollback:
1. Revert commit dbad240 (feat/mvp-2-source-expansion)
2. New modules `collection/hf_papers.py` and `collection/hn_algolia.py` are deleted
3. CLI falls back to `rss`-only path (no dispatch map)
4. Remove HF + HN + P2 entries from `sources.yaml` (9 P1 RSS entries remain + 1 legacy P2 if any)
5. No schema change, no data migration required
6. `data/` directory (gitignored) remains unchanged

## Impact on Existing Systems

**NO breaking changes**:
- `feed-collection` spec unchanged (RSS/Atom unchanged; P2 feeds reuse RssCollector)
- `item-storage` spec unchanged (no schema change)
- `item-deduplication` spec unchanged (existing canonical-URL + title-hash already handles JSON items)
- `hybrid-filter` unchanged (score thresholding happens at collection, not filter level)

**Additive changes only**:
- New collectors: HfPapersCollector, HnAlgoliaCollector
- New config fields: AIOBS_HF_MIN_UPVOTES, AIOBS_HN_MIN_POINTS
- CLI dispatch map added (no behavior change for existing RSS sources)
- 16 new sources in sources.yaml (2 JSON P1 + 14 RSS P2)

## Next Steps

### MVP-2 Completion Status
MVP-2 is now COMPLETE with all 3 slices delivered and archived:
1. **Slice 1**: ollama-adapter (MVP-2 LLM adapter rebase) — ✓ DONE
2. **Slice 2**: hybrid-filter (Score-based filtering with noise reduction) — ✓ DONE
3. **Slice 3**: mvp-2-source-expansion (JSON APIs + P2 feeds) — ✓ DONE (THIS ARCHIVE)

### MVP-3: Weekly Briefing (Next major milestone)
**Goal**: Synthesize top ≤10 ranked topics per day into a weekly briefing.

**Recommended sequence**:
1. `sdd-new` for MVP-3 proposal (weekly briefing scope, synthesis approach, LLM ranking integration)
2. Design phase: decide whether to use existing Item.score (in raw) or implement Item.score column
3. Implement: extend hybrid-filter to support top-K ranking by composite score; add synthesis CLI
4. Integrate: launchd scheduling for Friday briefing generation
5. Verify: end-to-end briefing generation against 7-day item window

**Known dependencies**:
- LLM adapter (ollama-adapter) already in place
- Score mechanism in place (upvotes/points in raw; priority-based ranking functional)
- Dedup and storage stable
- Scheduling framework (launchd) available but not yet wired

## Archive Closure

This archive marks the completion of the mvp-2-source-expansion SDD cycle:
- Proposal (intent clarified) → Spec (requirements defined) → Design (architecture solid) → Tasks (work planned) → Apply (code delivered) → Verify (all tests passing) → Archive (specs merged, cycle closed)

The change is now closed and immutable in this archive. All future work references MVP-3.
