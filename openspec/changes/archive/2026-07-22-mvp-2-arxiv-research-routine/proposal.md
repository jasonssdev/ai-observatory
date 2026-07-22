# Proposal: MVP-2 Deterministic Routine for Research/arXiv Categories

## Intent

MVP-2's signal-quality bar (`docs/roadmap.md`: "suppress the routine... you trust it
without cross-checking") is not met for individual research/arXiv papers. Validated live
2026-07-22: `mistral:7b` marked 33 arXiv papers SIGNIFICANT (~42% of its 79 SIGNIFICANT
verdicts, ~half the day's Significant section), burying real P1 lab news. Root cause:
arXiv/research feeds are P2, so they match no deterministic rule and flow to the LLM,
which — despite an already-hardened, arXiv-aware prompt (`build_prompt` carries the
"ROUTINE = individual arXiv papers" rubric + anti-example) — does not reliably follow the
exception on a 7B model. Prompt hardening is already in place and is NOT the fix; a
deterministic rule is. This slice adds a `category`-driven deterministic rule that routes
research-category items to ROUTINE before the LLM, removing ~33 LLM calls/run and
restoring trust in the Significant section.

## Scope

### In Scope
- MODIFY `synthesis/filter.py::score()`: add a deterministic `category-routine` rule that
  returns ROUTINE when `item.category` is in the configured routine-category set. Placed
  AFTER P1 auto-keep and score-keep, BEFORE the noise-keyword rule / LLM. Pure, defensive
  (missing/empty category -> no fire), no signature change.
- MODIFY `config.py`: new `filter_routine_categories: frozenset[str]` from
  `AIOBS_FILTER_ROUTINE_CATEGORIES` (comma-separated -> lowercased/trimmed frozenset) via
  a new parser helper. **Default ON = `{"research"}`** (see Key Decisions).
- Tests: `test_filter.py` (rule + precedence + LLM short-circuit), `test_config.py`
  (parser helper + default).
- Daily-record split behavior: research items land in set-aside/ROUTINE, not Significant.

### Out of Scope (non-goals)
- No change to collection, dedup, storage schema, or MVP-3 synthesis.
- No `sources.yaml` change (categories already correct).
- No change to P1 auto-keep or the score-keep rule.
- No `Item`/DB schema change, no new modules, no `classify_items`/`score()` signature change.
- Prompt/`build_prompt` is unchanged (optional one-line anti-example is deferred, not required).
- Ollama structured-output/`format:json` adapter stays out of scope.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `hybrid-filter`: ADD a "Deterministic Routine for Research Categories" requirement
  (category-in-set -> ROUTINE, placed after both auto-keep rules and before the LLM;
  auto-keep precedence preserved) + scenarios; EXTEND the configuration-thresholds
  requirement with `AIOBS_FILTER_ROUTINE_CATEGORIES` (default `{"research"}`, blank ->
  disabled).

## Approach

Exploration **Approach 1** (deterministic category-routine rule). `Item.category`
(persisted, sourced from `sources.yaml`'s fixed vocabulary: lab, research, newsletter,
news, tooling, community) cleanly identifies research/arXiv without brittle display-name
matching. Because the rule sits AFTER both SIGNIFICANT auto-keep tiers, it only reaches
non-auto-kept (P2+) research items — exactly the target set — while P1 HF Daily Papers
and any high-score research still stay SIGNIFICANT. The config surface mirrors the proven
score-keep opt-in shape: a normalized frozenset, fail-safe parse (blank/unset -> empty ->
disabled, never raises).

### Key Decisions
| # | Decision |
|---|----------|
| 1 | **`category`-based discriminator, not source names.** Uses the already-modeled `category` column; no string parsing, no schema/`sources.yaml` change. |
| 2 | **New rule after both auto-keep rules, before the LLM.** Precedence: (1) P1 auto-keep; (2) score-keep; (3) **category-routine [NEW]**; (4) noise-keyword; (5) None -> LLM. Genuinely high-priority/high-score research is still kept. |
| 3 | **Default ON = `{"research"}` (RECOMMENDED — needs user confirm).** Fixes the reported arXiv-as-signal leak out of the box and matches the roadmap "suppress the routine" bar and the user's stated intent. Tradeoff: unlike the score-keep precedent (default OFF/opt-in), this CHANGES current behavior on upgrade, and ALSO routes Google Research (P2, category=research) to ROUTINE. Default-OFF (empty) would preserve today's behavior but leave the bug unfixed until an operator opts in. **Recommended default-ON; flagged as the user's call to confirm.** |
| 4 | **Defensive read.** Missing/empty/unknown `category` or empty config set -> rule simply doesn't fire (falls through to keyword/LLM). Never raises. |

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/filter.py` | Modified | Add category-routine rule in `score()` after score-keep. |
| `src/ai_observatory/config.py` | Modified | `filter_routine_categories` field + frozenset parser helper; default `{"research"}`. |
| `tests/unit/test_filter.py` | Modified | Rule + precedence + LLM short-circuit scenarios; `_config` helper gains field. |
| `tests/unit/test_config.py` | Modified | Parser helper: unset -> default, blank/invalid -> disabled, valid -> parsed set. |
| `openspec/specs/hybrid-filter/spec.md` | Modified | New routine-categories requirement + config extension. |

## Testing Plan (strict TDD — `uv run pytest`, `uv run ruff check .`)
Mandatory cases:
- Research-category item -> ROUTINE via `score()`; via `classify_items` the LLM is NOT
  called (`client.calls == 0`).
- Precedence: P1 research (HF Daily Papers) stays SIGNIFICANT; high-score research stays
  SIGNIFICANT (both auto-keep before the routine rule fires).
- Non-research item (e.g. category=news, tooling) -> rule doesn't fire (LLM reached).
- Disabled: empty/blank config set -> rule doesn't fire even for research items.
- Raised `filter_keep_priority=2`: a P2 research item is auto-kept SIGNIFICANT before the
  routine rule (ordering correctness).
- Defensive: missing/empty/unknown `category` -> no exception, rule doesn't fire.
- Config: default `{"research"}` when unset; parsed lowercased/trimmed set when set;
  blank/invalid -> empty (disabled).

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Over-suppression: Google Research (P2 research) routed to ROUTINE hides an occasional notable post | Med | Config-driven — narrow the set or switch to a source allowlist later; surface for real-run tuning. |
| Default-ON changes current behavior on upgrade | Med (intended) | Documented in changelog/spec; single env var reverts (`AIOBS_FILTER_ROUTINE_CATEGORIES=`); confirmed with user as a product decision. |
| `category` free-text from YAML; typo/renamed value silently won't match | Low | Fixed vocabulary; loader requires the key; normalized (lowercased/trimmed) compare. |
| Interaction with raised `filter_keep_priority` mis-ordered | Low | Explicit ordering test (P2 auto-keep precedes routine rule). |

## Rollback Plan
Config-driven, reversible without a code revert: set `AIOBS_FILTER_ROUTINE_CATEGORIES=`
(empty) to disable the rule and restore today's LLM path. Otherwise revert the change
branch. No schema change, no data unwind (`data/` is gitignored). Past daily records are
unaffected (rule runs at classification time).

## Dependencies
None new. Reuses the existing `Config`, `Item.category` column, and pure `score()` seam.
Unit tests use the existing injected `LLMClient` mock — never live Ollama.

## Success Criteria
- [ ] With default `{"research"}`, individual arXiv/research (P2) items are ROUTINE with no LLM call.
- [ ] P1 research (HF Daily Papers) and high-score research remain SIGNIFICANT.
- [ ] With the config set empty, behavior falls back to today's LLM path for research items.
- [ ] Missing/unknown category never raises inside `score()`.
- [ ] `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 400 changed lines)
Estimate ~120-180 changed lines: `filter.py` delta (~10-20), `config.py` delta (~15-25),
`test_filter.py` (~60-90), `test_config.py` (~15-25), spec delta (~20-30). Small,
cohesive, single-PR slice. `400-line budget risk: Low`. `Chained PRs recommended: No`.
`Decision needed before apply: Yes` — confirm the default-ON `{"research"}` policy.

## Proposal question round (one open product decision)
The exploration surfaced one genuine product fork carried into this proposal:
**default the routine-category set ON (`{"research"}`, recommended) or OFF (opt-in)?**
This proposal assumes **default-ON with `research`** per the roadmap "suppress the
routine" bar and the user's stated intent to fix the arXiv-as-signal leak out of the box.
Assumption to confirm: default-ON also routes **Google Research (P2, category=research)**
to ROUTINE. If suppressing Google Research is undesirable, either (a) keep default-ON and
narrow later via config, or (b) switch to a source allowlist discriminator. No further
question round required unless the user wants to reconsider this default.
