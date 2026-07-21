# Design: Bound Daily-Record Rendering to a Recent Window

## Technical Approach

Push the deterministic "which dates to regenerate" rule into a pure,
unit-testable helper and confine the untestable wall-clock read to a single
line at the CLI edge (`cli.py:47`). `Config` gains its first non-`str` field via
a fail-safe `_int_env` parser. The DB stays the unbounded source of truth
(`db.upsert_items`, `db.items_for_date` unchanged); only the SET of `.md` files
written by the render loop (`cli.py:49-53`) is bounded.

## Architecture Decisions

### Decision: Helper placement & signature

**Choice**: Add `dates_within_window(candidate_dates: set[date], today: date, window_days: int) -> set[date]` to `src/ai_observatory/storage/records.py`.
**Alternatives considered**: New `storage/windowing.py` module; place in `config.py`; place in `collection/`.
**Rationale**: `records.py` already owns the "daily record" domain (`render_markdown`, `write_record`) and imports `date`. Selecting *which* daily records to regenerate is the same cohesion boundary as rendering them. A dedicated module fragments a ~60-line concern; `config.py` is wiring-only; `collection/` is ingestion, not output. Existing `tests/unit/test_records.py` already covers this module. Pure function → trivially testable with any injected `today`.

### Decision: Config int field + fail-safe parse

**Choice**: Add `record_window_days: int` to the frozen `Config`; parse via a module-level `_int_env(name, default)`; constant `_DEFAULT_RECORD_WINDOW_DAYS = 7`.
**Alternatives considered**: Inline `int(os.environ.get(...))` in `from_env`; parse at the CLI.
**Rationale**: A reusable parser isolates the first non-str field and its fail-safe contract (missing/invalid/negative → default). Inline parsing would leak `try/except` into `from_env` and could re-raise on bad input — reintroducing the 655-file explosion risk. Keeping `Config` frozen preserves the existing immutability convention.

```python
_DEFAULT_RECORD_WINDOW_DAYS = 7

def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default
```

`from_env` adds: `record_window_days=_int_env("AIOBS_RECORD_WINDOW_DAYS", _DEFAULT_RECORD_WINDOW_DAYS)`.

### Decision: `today` injectability without monkeypatching the clock

**Choice**: Extract a thin private seam `_write_daily_records(connection, records_dir, candidate_dates, today, window_days)` in `cli.py`. `collect()` reads `today = datetime.now(UTC).date()` once and delegates. The seam calls `records.dates_within_window(...)` then runs the existing write loop over the filtered set.
**Alternatives considered**: Default-arg `today=None` on a helper; monkeypatch `datetime` in the smoke test; keep everything inline in `collect()`.
**Rationale**: The seam is import-and-call testable with an in-memory DB and an explicit `today`, giving a CLI-level deterministic window assertion with zero clock patching. `datetime.now` stays on exactly one line inside `collect()` — the untestable boundary. Default-arg `None` adds branch logic for no gain; monkeypatching wall-clock is the brittleness we are eliminating.

## Data Flow

    collect() ── datetime.now(UTC).date() ─→ today   [CLI edge, untestable]
        │
        │ candidate_dates = {item.published_at.date()} ∪ {today}
        ▼
    _write_daily_records(conn, records_dir, candidate_dates, today, window_days)
        │
        ▼
    records.dates_within_window(candidate_dates, today, window_days)   [pure]
        │  keep d where (today - window_days) <= d <= today ; today always in
        ▼
    for d in filtered: items_for_date → render_markdown → write_record

Window semantics: `window_days >= 0` keeps `[today - window_days, today]`;
`window_days == 0` → `{today}` only; `today` is always included; dates after
`today` (future-dated items) are excluded.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/config.py` | Modify | Add `record_window_days: int`, `_int_env`, `_DEFAULT_RECORD_WINDOW_DAYS` |
| `src/ai_observatory/storage/records.py` | Modify | Add pure `dates_within_window` |
| `src/ai_observatory/cli.py` | Modify | Add `_write_daily_records` seam; `collect()` computes `today`, delegates filtered loop |
| `tests/unit/test_records.py` | Modify | `TestDatesWithinWindow` |
| `tests/unit/test_config.py` | Modify | Window default/override/invalid/negative/zero |
| `tests/integration/test_collect_integration.py` | Modify | Deterministic window assertion via injected `today` |

## Interfaces / Contracts

```python
def dates_within_window(
    candidate_dates: set[date], today: date, window_days: int
) -> set[date]: ...
```

## Testing Strategy (Strict TDD, red-first)

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (helper) | inside; lower boundary `today-window_days`; just-outside `-1`; `window_days==0`→today-only; today-always (absent from candidates); future-dated excluded; empty set→`{today}` | Pure calls, fixed `today=date(2026,7,20)` |
| Unit (config) | default 7 (unset); valid "3"→3; "0"→0; "abc"→7; "-1"→7 | `monkeypatch.setenv/delenv` |
| Integration | Seed in-memory DB across in-window, out-of-window, and future dates; call `_write_daily_records(conn, dir, candidates, today, 7)`; assert exactly in-window + `today` `.md` files exist, out-of-window date file absent | Injected `today`, no clock patch |
| Smoke | Existing `collect` tests stay green (exit 0, ≥1 file) | Unchanged |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration. DB and existing `.md` files untouched. Anchoring the window to
`today` makes same-day re-runs produce an identical file set (idempotent). The
655 out-of-window historical files are intentionally left in place; deletion is
a separate future change and is out of scope here.

## Open Questions

- None.
