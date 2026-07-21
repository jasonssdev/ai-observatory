# Proposal: MVP-2 Deterministic Score-Keep Signal Rule

## Intent

The deterministic filter layer promised in `docs/roadmap.md` (L42: "source priority +
keyword/score thresholds") is only half built. Today `synthesis/filter.py::score()`
uses source-priority auto-keep and noise-keyword drop, but the numeric popularity
score (HF upvotes / HN points) is collected, retained in `Item.raw`, and then IGNORED
by the filter. Genuinely viral items still go to the LLM (or get dropped by a keyword)
instead of being auto-kept. This slice adds the missing THIRD deterministic rule:
`score >= per-source keep threshold -> SIGNIFICANT` without an LLM call, mirroring the
P1 auto-keep. Small (~1-day) enhancement, no redesign.

## Scope

### In Scope
- MODIFY `collection/hf_papers.py` + `collection/hn_algolia.py`: stamp additive
  namespaced keys `raw["signal_score"]` (int) + `raw["signal_scale"]`
  (`"hf_upvotes"` | `"hn_points"`) into the existing raw payload; update the raw
  docstring note (additive keys, original entry preserved).
- MODIFY `synthesis/filter.py::score()`: add the score-keep rule in the positive
  auto-keep tier (read `signal_score`/`signal_scale`, compare to the matching config
  threshold, return SIGNIFICANT/DETERMINISTIC when at/above). Defensive parse — never
  raises. No signature change.
- MODIFY `config.py`: `filter_hf_keep_upvotes` / `filter_hn_keep_points`
  (`int | None`, default `None`) via a new `_optional_int_env` helper.
- Tests: `test_filter.py` (score-keep scenarios), `test_hf_papers.py` /
  `test_hn_algolia.py` (new raw keys), `test_config.py` (optional-int + None defaults).

### Out of Scope (non-goals)
- No change to the LLM classification path, prompt, or `classify_items` control flow.
- No change to collection-time floors (`AIOBS_HF_MIN_UPVOTES` / `AIOBS_HN_MIN_POINTS`).
- No `Item.score` column / schema migration (raw key only).
- No weekly briefing, no scheduling, no new sources.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `hybrid-filter`: ADD an "Auto-Keep for High-Score Items" requirement (score-keep rule
  + scenarios); EXTEND the configuration-thresholds requirement with the two optional
  keep thresholds (default `None` = disabled).
- `json-collection`: HF/HN collectors retain a NORMALIZED `signal_score` + `signal_scale`
  in `raw`. A raw-key addition, NOT an `Item.score` column (column remains a non-goal).

## Approach

Exploration **Approach A**. The two JSON collectors own payload knowledge and normalize
their native score into a stable cross-layer contract in `raw`: `signal_score` (int) +
`signal_scale` (source-set tag). RSS emits neither key. The pure `score()` reads this one
stable contract, maps `signal_scale` -> the matching per-source config threshold, and
auto-keeps at/above it — staying source-agnostic and free of collection payload shapes
(rejecting Approach B's layering coupling and Approach C's schema migration). Reads are
fully defensive: missing/None/non-int `signal_score`, a `None` threshold, or malformed
raw all make the rule simply not fire (fall through to keyword/LLM). Out-of-the-box
behavior is IDENTICAL to today until an operator sets a threshold.

### Key Decisions
| # | Decision |
|---|----------|
| 1 | **Approach A — collectors normalize into `raw`.** HF/HN stamp `raw["signal_score"]` (int) + `raw["signal_scale"]` (`"hf_upvotes"`/`"hn_points"`). `score()` reads this stable contract and maps scale -> the matching keep threshold. RSS has no keys -> rule never fires. Keeps `score()` pure and source-agnostic; clean hexagonal layering. |
| 2 | **New third rule in the positive auto-keep tier.** Precedence: (1) P1 source auto-keep -> SIGNIFICANT; (2) **score-keep -> SIGNIFICANT [NEW]**; (3) noise-keyword -> ROUTINE; (4) else None -> LLM. Score-keep sits BEFORE the noise-keyword drop, so a very-high-score item overrides a noise keyword (high score = strong signal). |
| 3 | **Opt-in, disabled by default.** New `filter_hf_keep_upvotes` / `filter_hn_keep_points` (`int | None`) from `AIOBS_FILTER_HF_KEEP_UPVOTES` / `AIOBS_FILTER_HN_KEEP_POINTS` via `_optional_int_env`. `None` = rule disabled for that source (default). Zero behavior change until configured. Documented starter values (HF ~50, HN ~200) in prose only — NOT defaults. `0` cannot disable (score>=0 is always true), hence None-sentinel. |
| 4 | **Defensive read.** Reading `signal_score` inside the pure `score()` must NEVER raise: missing / None / non-int / malformed raw -> rule simply doesn't fire. |

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/collection/hf_papers.py` | Modified | Stamp `signal_score`/`signal_scale` into `raw` (additive); docstring note. |
| `src/ai_observatory/collection/hn_algolia.py` | Modified | Stamp `signal_score`/`signal_scale` into `raw` (additive); docstring note. |
| `src/ai_observatory/synthesis/filter.py` | Modified | Add score-keep rule + defensive raw parse in `score()`. |
| `src/ai_observatory/config.py` | Modified | Two optional keep-threshold fields + `_optional_int_env`. |
| `tests/unit/test_filter.py` | Modified | Score-keep scenarios; `_config` helper gains the two fields (default None). |
| `tests/unit/{test_hf_papers,test_hn_algolia}.py` | Modified | Assert normalized `signal_score`/`signal_scale` in `raw`. |
| `tests/unit/test_config.py` | Modified | Optional-int env parse + None defaults + invalid/negative -> None. |

## Testing Plan (strict TDD — `uv run pytest`, `uv run ruff check .`)
Mandatory cases:
- Score `>=` keep threshold -> SIGNIFICANT via `score()`; via `classify_items` the LLM
  is NOT called (`client.calls == 0`).
- Score present but BELOW keep -> falls through to keyword/None path (LLM reached).
- Score exactly AT threshold (`>=`) boundary -> SIGNIFICANT.
- RSS item (raw has no score key) -> rule doesn't fire.
- Per-source independence: HN threshold set + HF `None` (and vice versa) -> only the
  configured source auto-keeps.
- Threshold `None` (unset) with score present -> rule disabled (falls through).
- Precedence: noise-keyword item WITH high score -> SIGNIFICANT (score-before-noise).
- Defensive: malformed / empty raw (`"{}"`, non-JSON) -> no exception, rule doesn't fire.
- Collectors: HF and HN each retain `signal_score` (int) + `signal_scale` (correct tag)
  in `raw`, original payload keys preserved.
- Config: default `None` when unset; parsed int when set; invalid/negative -> `None`.

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Score-keep-before-noise ordering keeps a viral "funding round" item | Med | Intended per decision #2 (high score = strong signal); thresholds set well above floors so only viral items qualify; surface for tuning. |
| Malformed/non-int raw raises inside the pure `score()` | Low | Mandatory defensive test; try/except-guarded parse; rule silently no-ops. |
| Approach A bends the `Item.raw` "original entry" docstring | Low | Keys namespaced + additive; original keys preserved; docstring note updated. |
| Wrong scale threshold applied (HF vs HN mixed) | Low | Explicit `signal_scale` tag drives selection; per-source independence test. |
| On-by-default would inflate SIGNIFICANT + skip LLM unexpectedly | Low | Opt-in `None` default; zero change until configured; starter values documented only. |

## Rollback Plan
Additive, opt-in enhancement. Revert the change branch. The `raw` keys are additive and
harmless if unread; with both thresholds `None` (default) the new rule never fires, so
behavior is identical to today even without a revert. No schema change, no data unwind
(`data/` is gitignored).

## Dependencies
None new. Reuses the existing `Config`, `Item.raw`, and pure `score()` seam. Unit tests
use the existing injected `LLMClient` mock — never live Ollama.

## Success Criteria
- [ ] With a keep threshold set, a viral HF/HN item is auto-kept SIGNIFICANT with no LLM call.
- [ ] With thresholds unset (`None`), behavior is byte-for-byte identical to today.
- [ ] HF/HN `raw` carries `signal_score` + `signal_scale`; RSS carries neither.
- [ ] Malformed raw never raises inside `score()`.
- [ ] `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 800 changed lines)
Estimate ~180-260 changed lines: `filter.py` delta (~25-40), two collector deltas
(~10-15 each), `config.py` delta (~20-30), `test_filter.py` (~80-110), collector tests
(~20-30), `test_config.py` (~15-25). Small, cohesive, single-PR slice.
`400-line budget risk: Low`. `Chained PRs recommended: No`.
`Decision needed before apply: No`.
