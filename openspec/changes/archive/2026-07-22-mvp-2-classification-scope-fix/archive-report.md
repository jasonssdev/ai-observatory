# Archive Report: MVP-2 Classification Scope Fix

**Change**: mvp-2-classification-scope-fix
**Archived**: 2026-07-22
**Verdict**: Fully implemented, verified PASS (0 CRITICAL, 1 WARNING, 0 SUGGESTION), and archived. Change widened classification from 1 day to 7-day render window, fixing a critical production bug where 0 items were classified.

## SDD Artifacts Archived

This archive contains the complete artifact trail for the MVP-2 Classification Scope Fix change, closing the SDD cycle.

### Artifact Observation IDs (Engram traceability)

| Artifact | Topic Key | Observation ID | Status |
|----------|-----------|---|---|
| Proposal | sdd/mvp-2-classification-scope-fix/proposal | 1497 | Complete |
| Exploration | sdd/mvp-2-classification-scope-fix/exploration | 1496 | Complete |
| Spec | sdd/mvp-2-classification-scope-fix/spec | 1499 | Complete |
| Design | sdd/mvp-2-classification-scope-fix/design | 1501 | Complete |
| Tasks | sdd/mvp-2-classification-scope-fix/tasks | 1503 | 24/24 complete |
| Apply Progress | sdd/mvp-2-classification-scope-fix/apply-progress | 1505 | Complete |
| Verification Report | sdd/mvp-2-classification-scope-fix/verify-report | 1506 | PASS |

### Archived Contents

- `proposal.md` — Intent (3105 items collected, 0 classified), root cause (classification scope = run-day, render scope = 7-day window), scope, approach, 5 key decisions, rollback plan
- `exploration.md` — Root-cause diagnosis from live usage validation, symptom, confirmed root cause, affected code areas
- `design.md` — Technical approach, 5 architecture decisions, data flow, 5 file changes, interface contracts, testing strategy, threat matrix
- `tasks.md` — 24 implementation tasks across 5 phases (all checked), TDD cycle evidence, work unit evidence
- `verify-report.md` — Full verification with 186/186 tests passing, 0 CRITICAL, 1 WARNING, 0 SUGGESTION
- `specs/` — 3 delta specifications (3 ADDED requirements)

## Specifications Synced to Main Specs

Three domain specifications were synchronized with delta merges:

### Synced to `openspec/specs/`

| Domain | Status | Details |
|--------|--------|---------|
| hybrid-filter | Merged | DELTA ADDED: "Classification Scope Matches the Render Window" (4 scenarios: in-window prior-day classified, out-of-window excluded, idempotency holds, run-level LLM fallback holds) — widens classification from run-day to 7-day render window |
| item-storage | Merged | DELTA ADDED: "Query Unclassified Items Within a Window" (2 scenarios: window query returns in-range, excludes classified/out-of-range) — new `unclassified_within(conn, start_date, end_date)` mirroring existing `unclassified_for_date` |
| collect-cli | Merged | DELTA ADDED: "End-of-Run Summary" (2 scenarios) + "Per-Source Failure Visibility" (2 scenarios) — run summary reporting sources/items/mode, per-source failures surfaced via logging |

**Note**: All three deltas are now integrated into the main specs at `openspec/specs/{hybrid-filter,item-storage,collect-cli}/spec.md`. Pre-existing requirements remain intact and unchanged.

## Verification Summary

**Verdict**: PASS (0 CRITICAL, 1 WARNING, 0 SUGGESTION)

- **Test Suite**: 186/186 passing (`uv run pytest`; baseline 177 → +9 new tests)
- **Lint**: All checks passed (`uv run ruff check .`)
- **Tasks**: 24/24 implementation tasks checked (all 5 phases complete)
- **Spec Coverage**: 4/4 hybrid-filter scenarios, 2/2 item-storage scenarios, 4/4 collect-cli scenarios test-covered
- **Critical Issues**: 0 (no blockers found)
- **Bug Fix Verification**: Regression test empirically reproduces pre-fix failure (0 verdicts on yesterday-dated items); fix confirmed via source inspection (classification now uses window-scoped query)

### Non-Blocking Findings

**WARNING:**
1. **Review-budget overage**: Actual changed lines (407 per apply-progress) exceed the 400-line review budget guard despite tasks.md forecast (180-260/Low). Overage concentrated in `tests/integration/test_collect_integration.py` (+262) due to 5 distinct new scenarios each needing full CLI-level fixture setup. Production code is small (63 lines across 3 files: records.py +11-1, db.py +23, cli.py +29-3) and low-risk (no auth/security/shell surface). Recommend orchestrator apply size/hot-path review-lens rule (likely full 4R given >400 lines) at post-apply review gate.

**SUGGESTION**: None.

All findings are non-blocking. Bug fix is proven by regression test and source inspection; scope-widening correctness guaranteed by single source of truth (records.window_start).

## Central Bug Fix Verification

**The bug was genuine and is fixed:**

**Pre-fix symptom**: `collect()` called `db.unclassified_for_date(conn, today)` which filtered `WHERE published_at LIKE '{today}%'` — items published on UTC run-day. Real feeds carry prior-day dates → query returned 0 items → 0 verdicts → all 3105 collected items rendered in "Set aside" bucket; hybrid filter was inert.

**Post-fix**: `collect()` now calls `db.unclassified_within(conn, start, end)` where `start = records.window_start(today, window_days)` (new function) and `end = today + timedelta(days=1)`. Queries `WHERE published_at >= start.isoformat() AND published_at < end.isoformat()` — items within the render window. Yesterday-dated items are now classified.

**Regression test proof**: `TestCollectClassifiesWithinWindowNotOnlyToday` — freeze `today=2026-07-21`, load items dated `2026-07-20` (yesterday, within 7-day window), run `collect()`, assert verdicts are assigned. Test fails against pre-fix code (reproduces `assert 0 > 0` bug), passes post-fix. Idempotent re-run test confirms already-classified items are skipped (via `label IS NULL` join condition).

## Single Source of Truth

**Window bounds consistency guaranteed:**

`records.window_start(today, window_days) -> date` is the sole definition of the render window's lower bound (lines 20-27 in records.py). `dates_within_window` now delegates to it (line 39: `earliest = window_start(today, window_days)`). `collect()` calls the same function (cli.py:115). Both classification and render bounds derive from one function — no independent recomputation exists (verified via ripgrep).

## Rollback

This is a scope-widening fix with no destructive changes:

- Revert the feature branch (commit a7f853c)
- Delete the new `unclassified_within` function from db.py (additive, safe to remove)
- Revert modifications to `cli.py`, `db.py`, `records.py`
- No schema migration or data change required
- Reverting restores prior (run-day-only) classification behavior

## Known Deferred Limitations

The following limitations are intentionally deferred to future releases and are recorded here for visibility:

| Limitation | Target | Notes |
|-----------|--------|-------|
| LLM verdict parser signal-quality hardening | separate filter-signal-quality change | Current parser over-matches "significant" via naive substring, classifying ~99% as significant; fix will harden parse_verdict + tighten the prompt. Also address: httpx INFO logs are noisy under the new logging.basicConfig — scope httpx to WARNING in signal-quality change. |
| Full structured logging / source-health dashboard | v1.0 | Typer.echo summary suffices for MVP-2; structured logging deferred. |
| Per-source thresholds (config-driven noise keywords) | MVP-3 or later | Keywords currently in filter.py defaults; scalar-only config acceptable for tuning. |

## Next Steps

The MVP-2 Classification Scope Fix is complete and closed. The next phase depends on the project roadmap:

**Immediate follow-up**: Signal-quality filter hardening (separate `filter-signal-quality` change) — harden the LLM verdict parser to reduce false positives and configure logging levels per source module.

**Next MVP-2 slice**: Source expansion (HF Daily Papers, HN Algolia, P2 feeds) — adds multi-source coverage to the now-working hybrid filter, ready to classify expanded feed corpus.

**Beyond MVP-2**: Weekly briefing, scheduling, and the `synthesize --daily/--weekly` CLI are roadmap items for MVP-3 (automated synthesis phase).

---

**Archive prepared**: 2026-07-22
**SDD Cycle**: Complete
**Status**: Ready for production merge and release.
**Delivery Strategy**: Single PR (407 lines; budget exception accepted). Bug fix verified PASS with regression test. No regressions (186/186 tests green).
