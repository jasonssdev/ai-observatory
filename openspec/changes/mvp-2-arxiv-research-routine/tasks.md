# Tasks: MVP-2 Deterministic Routine for Research/arXiv Categories

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~220-320 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast (session-provided; review budget raised to 800) |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Config `_frozenset_env` + `filter_routine_categories` field, `_normalize_category` + category-routine rule in `score()`, full test coverage | PR 1 (only) | `uv run pytest tests/unit/test_config.py tests/unit/test_filter.py -q` | N/A — pure functions/config, no external runtime scenario; full suite (`uv run pytest`) is the harness | Revert branch; set `AIOBS_FILTER_ROUTINE_CATEGORIES=` to disable without code revert |

## Phase 1: Configuration (Foundation)

- [x] 1.1 RED — `tests/unit/test_config.py`: `_frozenset_env` unset -> `default`; present blank/whitespace/commas-only -> empty frozenset; normalizes strip+casefold, drops empties.
- [x] 1.2 RED — `tests/unit/test_config.py`: `Config.from_env` `filter_routine_categories` defaults `{"research"}` when unset; override parsed/normalized (`" Research, Lab "` -> `{"research","lab"}`); blank env var disables (empty frozenset).
- [x] 1.3 GREEN — `src/ai_observatory/config.py`: add `_frozenset_env(name: str, default: frozenset[str]) -> frozenset[str]` helper (mirrors `_int_env`; default applies only when unset).
- [x] 1.4 GREEN — `src/ai_observatory/config.py`: add `filter_routine_categories: frozenset[str]` field, wired from `AIOBS_FILTER_ROUTINE_CATEGORIES` via `_frozenset_env`, default `frozenset({"research"})`.
- [x] 1.5 REFACTOR — `uv run pytest tests/unit/test_config.py -q` + `uv run ruff check src/ai_observatory/config.py`.

## Phase 2: Filter Category-Routine Rule

- [x] 2.1 `tests/unit/test_filter.py`: extend `_config` helper with `filter_routine_categories: frozenset[str] = frozenset()` kwarg so existing tests keep the rule disabled by default.
- [x] 2.2 `tests/unit/test_filter.py`: extend `_item` helper with a `category: str = "lab"` kwarg.
- [x] 2.3 RED — non-P1 item, `category="research"`, default set -> `score() == ROUTINE` (spec scenario 1).
- [x] 2.4 RED — P1 + `category="research"` -> `SIGNIFICANT` via auto-keep; routine rule never fires (scenario 2).
- [x] 2.5 RED — score-keep threshold met + `category="research"` -> `SIGNIFICANT` via score-keep; routine rule never fires (scenario 3).
- [x] 2.6 RED — `category="news"` -> routine rule does not fire; noise-keyword/LLM path unchanged (scenario 4).
- [x] 2.7 RED — empty `filter_routine_categories` + `category="research"` -> rule does not fire, falls through (scenario 5).
- [x] 2.8 RED — `filter_keep_priority=2`, `source_priority=2`, `category="research"` -> `SIGNIFICANT` via priority auto-keep before routine rule runs (scenario 6).
- [x] 2.9 RED — `category` missing/empty/unrecognized -> no exception raised, rule does not fire (scenario 7, defensive).
- [x] 2.10 RED — `classify_items` on a `category="research"` item -> `client.calls == 0`, result is `Significance(label=ROUTINE, mode=DETERMINISTIC)` (LLM short-circuit; confirms scenario 8 daily-record placement reuses existing `Significance`/db plumbing — no new production code needed there).
- [x] 2.11 GREEN — `src/ai_observatory/synthesis/filter.py`: add `_normalize_category(value: str) -> str` (strip + casefold).
- [x] 2.12 GREEN — `src/ai_observatory/synthesis/filter.py`: add category-routine rule inside `score()`, placed after the score-keep rule and before the noise-keyword rule; guard on non-empty `item.category` and non-empty `config.filter_routine_categories`.
- [x] 2.13 REFACTOR — `uv run pytest tests/unit/test_filter.py -q` + `uv run ruff check src/ai_observatory/synthesis/filter.py`.

## Phase 3: Final Verification

- [x] 3.1 `uv run pytest` — full suite green, no regressions.
- [x] 3.2 `uv run ruff check .` — clean.
- [x] 3.3 Cross-check all 8 `hybrid-filter` spec-delta scenarios (new requirement + config extension) against an executed test case.
