# Proposal: Bound Daily-Record Rendering to a Recent Window

## Intent

Cold-start ingestion of the RSS backlog (items dating to 2015) makes the collector
regenerate one Markdown file per distinct published-date — a 655-file explosion.
Rendering must reflect only recent activity while the DB stays the complete source
of truth. Bound the SET of regenerated `.md` files to a recent window; leave
ingestion unbounded.

## Scope

### In Scope
- New config `AIOBS_RECORD_WINDOW_DAYS` (int, default 7). Invalid/negative → fail-safe fallback to default.
- Pure helper `dates_within_window(candidate_dates, today, window_days) -> set[date]`; `cli.py` computes `today = datetime.now(UTC).date()` at the edge and delegates filtering.
- Window = last N days + the run's UTC date; run date ALWAYS included, even when `window_days == 0`.
- Spec deltas to `daily-record` and `collect-cli`.

### Out of Scope
- Ingestion/INSERT filtering — DB remains unbounded source of truth.
- Deletion of the 655 pre-existing historical `.md` files (future cleanup change).
- LLM, scheduling.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `daily-record`: regenerated set bounded to published-dates within window + run UTC date; add cold-start-backlog scenario; note ingestion unbounded.
- `collect-cli`: add `AIOBS_RECORD_WINDOW_DAYS` to config wiring + default-7 scenario.

## Approach

Confine the untestable inline `datetime.now(UTC)` (`cli.py:47`) to the CLI edge and
push the deterministic rule into a pure, unit-testable helper (Strict TDD). `cli.py:46-53`
builds `candidate_dates`, injects `today`, then loops over the bounded set returned
by the helper. Config gains its first non-`str` field via an `_int_env` parse helper
in `config.py` (`_DEFAULT_RECORD_WINDOW_DAYS = 7`) with try/except validation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/config.py` | Modified | New `record_window_days: int`, fail-safe parse |
| `src/ai_observatory/records.py` (or new `windowing`) | New | Pure `dates_within_window` helper |
| `src/ai_observatory/cli.py:46-53` | Modified | Compute `today`, delegate filter |
| `openspec/specs/daily-record/spec.md:30-38` | Modified | Bound regeneration set |
| `openspec/specs/collect-cli/spec.md:29-42` | Modified | Config wiring + default |
| `tests/unit/*`, `tests/smoke/test_cli.py` | New/Modified | Helper + config + window tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `window=0` ambiguity | Med | Define explicitly: today only |
| Invalid env reintroduces explosion | Low | Fail-safe fallback to default 7 |
| Future-dated items never rendered | Low | Accepted; run date always rendered |
| Idempotency drift | Low | Window from `today` → same-day re-run identical |
| Old `.md` files linger | High | Intentional; left as-is, deletion out of scope |

## Rollback Plan

Revert the change; unset `AIOBS_RECORD_WINDOW_DAYS`. No data migration — DB and
existing `.md` files are untouched, so rollback restores prior render-all behavior.

## Dependencies

- None.

## Success Criteria

- [ ] Cold-start backlog generates only in-window + run-date files, not 655.
- [ ] `AIOBS_RECORD_WINDOW_DAYS` default 7; invalid/negative falls back to 7.
- [ ] `window=0` renders only the run UTC date.
- [ ] Same-day re-run produces an identical file set (idempotent).
