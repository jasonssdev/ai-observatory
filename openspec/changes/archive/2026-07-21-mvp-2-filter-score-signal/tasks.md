# Tasks: MVP-2 Deterministic Score-Keep Signal Rule

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~180-260 |
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
| 1 | Config helper + score-keep thresholds, collector signal injection, filter rule, docstring | PR 1 (only) | `uv run pytest tests/unit/test_config.py tests/unit/test_hf_papers.py tests/unit/test_hn_algolia.py tests/unit/test_filter.py -q` | N/A — pure functions/config, no external runtime scenario; full suite (`uv run pytest`) is the harness | Revert branch; both thresholds default `None` so behavior is unchanged even pre-revert |

## Phase 1: Configuration (Foundation)

- [x] 1.1 RED — `tests/unit/test_config.py`: `_optional_int_env` unset/blank -> `None`, valid int -> `int`, non-integer -> `None`, negative -> `None`.
- [x] 1.2 RED — `tests/unit/test_config.py`: `filter_hf_keep_upvotes`/`filter_hn_keep_points` default `None`; env override parses correctly.
- [x] 1.3 GREEN — `src/ai_observatory/config.py`: add `_optional_int_env(name) -> int | None` (mirrors `_int_env`, returns `None` instead of a default).
- [x] 1.4 GREEN — `src/ai_observatory/config.py`: add `filter_hf_keep_upvotes`/`filter_hn_keep_points` (`int | None`, default `None`) wired from `AIOBS_FILTER_HF_KEEP_UPVOTES`/`AIOBS_FILTER_HN_KEEP_POINTS` via `_optional_int_env`.
- [x] 1.5 REFACTOR — `uv run pytest tests/unit/test_config.py -q` + `uv run ruff check src/ai_observatory/config.py`.

## Phase 2: Collector Signal Injection

- [x] 2.1 RED — `tests/unit/test_hf_papers.py`: `json.loads(item.raw)["signal_score"] == paper.upvotes` (int), `["signal_scale"] == "hf_upvotes"`, original `upvotes` key preserved.
- [x] 2.2 RED — `tests/unit/test_hn_algolia.py`: `json.loads(item.raw)["signal_score"] == hit["points"]` (int), `["signal_scale"] == "hn_points"`, permalink/original keys preserved.
- [x] 2.3 GREEN — `src/ai_observatory/collection/hf_papers.py::parse_hf_papers`: inject `signal_score`/`signal_scale="hf_upvotes"` into entry dict before `json.dumps`.
- [x] 2.4 GREEN — `src/ai_observatory/collection/hn_algolia.py::parse_hn_algolia`: inject `signal_score`/`signal_scale="hn_points"` into entry dict before `json.dumps`.
- [x] 2.5 REFACTOR — `uv run pytest tests/unit/test_hf_papers.py tests/unit/test_hn_algolia.py -q`; confirm malformed/empty scenarios unaffected.

## Phase 3: Filter Score-Keep Rule

- [x] 3.1 RED — `tests/unit/test_filter.py`: `signal_score >= threshold` -> `SIGNIFICANT`, `client.calls == 0`.
- [x] 3.2 RED — `tests/unit/test_filter.py`: score meets threshold AND noise-keyword match -> `SIGNIFICANT` (precedence).
- [x] 3.3 RED — `tests/unit/test_filter.py`: score below threshold -> rule doesn't fire, falls through unchanged.
- [x] 3.4 RED — `tests/unit/test_filter.py`: threshold `None` -> never fires regardless of score.
- [x] 3.5 RED — `tests/unit/test_filter.py`: no `signal_score`/`signal_scale` (RSS-like) -> doesn't fire.
- [x] 3.6 RED — `tests/unit/test_filter.py`: HF-only and HN-only threshold matches classified independently per `signal_scale`.
- [x] 3.7 RED — `tests/unit/test_filter.py`: malformed raw / non-int `signal_score` / unknown `signal_scale` -> no exception, doesn't fire.
- [x] 3.8 GREEN — `src/ai_observatory/synthesis/filter.py`: add `json` import, `_SCALE_TO_THRESHOLD` map, new score-keep rule in `score()` between P1 auto-keep and noise-keyword rule (defensive `json.loads` wrapped in `try/except (TypeError, ValueError)`).
- [x] 3.9 REFACTOR — `uv run pytest tests/unit/test_filter.py -q` + `uv run ruff check src/ai_observatory/synthesis/filter.py`.

## Phase 4: Documentation

- [x] 4.1 `src/ai_observatory/storage/models.py`: update `Item.raw` docstring noting additive, namespaced `signal_score`/`signal_scale` keys injected by HF/HN collectors.

## Phase 5: Final Verification

- [x] 5.1 `uv run pytest` — full suite green, no regressions.
- [x] 5.2 `uv run ruff check .` — clean.
- [x] 5.3 Cross-check every scenario in `hybrid-filter` and `json-collection` spec deltas against an executed test case.

## Phase 6: Post-Verify Refactor (pure, zero behavior change)

Triggered by sdd-verify SUGGESTION: extract the popularity-signal `raw` contract (bare string literals `"signal_score"`/`"signal_scale"`/`"hf_upvotes"`/`"hn_points"` duplicated across collectors and filter.py) into a single source of truth.
- [x] 6.1 src/ai_observatory/storage/models.py: added `SIGNAL_SCORE_KEY`, `SIGNAL_SCALE_KEY` constants and `SignalScale(StrEnum)` (HF_UPVOTES, HN_POINTS); updated `Item.raw` docstring to reference the new names.
- [x] 6.2 src/ai_observatory/collection/hf_papers.py: import the constants/enum from storage.models; use them in the `raw` dict injection instead of bare literals.
- [x] 6.3 src/ai_observatory/collection/hn_algolia.py: same as 6.2.
- [x] 6.4 src/ai_observatory/synthesis/filter.py: import the constants/enum; `_SCALE_TO_THRESHOLD` keyed by `SignalScale` members; `_meets_score_keep_threshold` reads via `SIGNAL_SCALE_KEY`/`SIGNAL_SCORE_KEY`.
- [x] 6.5 Verification: `uv run pytest -q` -> 177 passed both before and after (0 new/removed/failed — pure refactor confirmed). `uv run ruff check .` -> All checks passed.

## Status: ALL TASKS COMPLETE (28/28 total: 23 original + 5 Phase 6 refactor). Ready for archive.
