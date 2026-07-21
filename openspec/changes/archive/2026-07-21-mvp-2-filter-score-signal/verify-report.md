```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:68b75ce-feat-mvp-2-filter-score-signal
verdict: pass
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 20/20
test_command: uv run pytest -q
test_exit_code: 0
test_output_hash: sha256:5dabc36325cca625f15dbebc7de816142f03d1e55e07a6154437b96480e30022
build_command: uv run ruff check .
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: mvp-2-filter-score-signal
**Version**: N/A (delta spec)
**Mode**: Strict TDD

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 28 |
| Tasks complete | 28 |
| Tasks incomplete | 0 |
| Note | 23 original implementation tasks + 5 Phase 6 post-verify refactor tasks (pure, zero behavior change) |

### Build & Tests Execution
**Build/Lint**: PASSED
```text
$ uv run ruff check .
All checks passed!
```

**Tests**: 177 passed / 0 failed / 0 skipped (baseline was 155; +22 new tests, matches apply-progress claim)
```text
$ uv run pytest -q
........................................................................ [ 40%]
........................................................................ [ 81%]
.................................                                        [100%]
177 passed in 0.35s
```

**Coverage**: Not available (no coverage tool configured in this project) — informational only, not blocking.

### Spec Compliance Matrix (hybrid-filter, ADDED: Deterministic Auto-Keep for High-Score Items)
| Scenario | Test | Result |
|---|---|---|
| High score is auto-kept, LLM never called | `test_filter.py::TestScoreKeepRule::test_score_at_or_above_threshold_is_significant` + `TestClassifyItemsScoreKeep::test_score_keep_verdict_never_reaches_llm` (asserts `client.calls == 0`) | COMPLIANT |
| High score overrides a noise keyword (precedence) | `test_filter.py::TestScoreKeepRule::test_score_keep_precedes_noise_keyword` | COMPLIANT |
| Below-threshold score falls through | `test_filter.py::TestScoreKeepRule::test_score_below_threshold_falls_through` | COMPLIANT |
| Disabled threshold (`None`) never fires | `test_filter.py::TestScoreKeepRule::test_threshold_none_never_fires` | COMPLIANT |
| RSS item (no signal keys) unaffected | `test_filter.py::TestScoreKeepRule::test_no_signal_keys_does_not_fire` | COMPLIANT |
| Per-source threshold independence (HF vs HN) | `test_filter.py::TestScoreKeepRule::test_hf_and_hn_thresholds_are_independent` | COMPLIANT |
| Malformed score never raises (bad JSON, non-int, bool, unknown scale) | `test_filter.py::TestScoreKeepRule::test_malformed_raw_does_not_raise`, `test_non_int_signal_score_does_not_fire`, `test_bool_signal_score_does_not_fire`, `test_unknown_signal_scale_does_not_fire` | COMPLIANT |

### Spec Compliance Matrix (hybrid-filter, MODIFIED: Configuration-Driven Thresholds)
| Scenario | Test | Result |
|---|---|---|
| Defaults apply when unset (both `None`) | `test_config.py::TestFilterScoreKeepThresholds::test_unset_defaults_to_none` | COMPLIANT |
| Overrides apply when set | `test_config.py::TestFilterScoreKeepThresholds::test_env_override_takes_effect` | COMPLIANT |
| Invalid override falls back to disabled (`None`), no raise | `test_config.py::TestFilterScoreKeepThresholds::test_invalid_value_falls_back_to_none` | COMPLIANT |
| Helper: unset/blank/non-integer/negative -> None, valid -> int, zero is valid | `test_config.py::TestOptionalIntEnv` (6 cases) | COMPLIANT |

### Spec Compliance Matrix (json-collection, MODIFIED: HF Daily Papers Parsing)
| Scenario | Test | Result |
|---|---|---|
| Valid HF payload normalizes `signal_score`/`signal_scale`, original `upvotes` preserved | `test_hf_papers.py::test_parse_injects_normalized_signal_score_and_scale` | COMPLIANT |
| Malformed/empty HF JSON yields no items (unchanged) | `test_hf_papers.py::test_parse_malformed_returns_empty_no_raise` (pre-existing, still green) | COMPLIANT |

### Spec Compliance Matrix (json-collection, MODIFIED: HN Algolia Parsing)
| Scenario | Test | Result |
|---|---|---|
| Valid HN payload normalizes `signal_score`/`signal_scale`, original `points`/permalink preserved | `test_hn_algolia.py::test_parse_injects_normalized_signal_score_and_scale` | COMPLIANT |
| Null external URL still falls back to permalink (unchanged) | `test_hn_algolia.py` pre-existing permalink-fallback test, still green | COMPLIANT |
| Malformed/empty HN JSON yields no items (unchanged) | `test_hn_algolia.py::test_parse_malformed_returns_empty_no_raise` (pre-existing, still green) | COMPLIANT |

**Compliance summary**: 20/20 scenarios compliant (7 hybrid-filter ADDED + 4 hybrid-filter MODIFIED-config + 2 HF + 3 HN = 16 explicit spec-listed scenarios, plus 4 additional guard-case tests (non-int, bool, unknown-scale as 3 separate assertions bundled under "malformed score never raises") — every scenario line in both spec deltas has at least one passing covering test; zero UNTESTED, zero FAILING).

### Correctness (Static Evidence)

**Precedence order in `synthesis/filter.py::score()` (lines 92-114)** — confirmed by direct source read:
1. `item.source_priority <= config.filter_keep_priority` -> `SIGNIFICANT` (P1, line 104-105)
2. `_meets_score_keep_threshold(item, config)` -> `SIGNIFICANT` (NEW rule, line 107-108) — placed strictly between P1 and the noise-keyword check.
3. Noise-keyword substring match -> `ROUTINE` (line 110-112)
4. Else `None` (UNCERTAIN, falls to LLM)

This exactly matches the locked design precedence table (P1 -> score-keep -> noise-keyword -> LLM) and is proven at runtime by `test_score_keep_precedes_noise_keyword`, which builds an item with BOTH a noise keyword title ("Funding round announced") AND a qualifying score, and asserts `SIGNIFICANT`.

**Defensive score read (`_meets_score_keep_threshold`, lines 61-89)** — confirmed by direct source read:
- `json.loads(item.raw)` wrapped in `try/except (TypeError, ValueError)` -> returns `False` on malformed raw, never raises.
- `isinstance(raw, dict)` guard rejects non-dict decoded payloads (e.g. a JSON array or scalar).
- `isinstance(score_value, int) and not isinstance(score_value, bool)` explicitly rejects `bool` — required because `isinstance(True, int) is True` in Python; without this guard a `signal_score: true` would incorrectly pass the int check. Covered by `test_bool_signal_score_does_not_fire`, which uses `filter_hf_keep_upvotes=0` specifically to prove the bool is rejected even though `True >= 0` would otherwise be truthy.
- Unknown `signal_scale` -> `_SCALE_TO_THRESHOLD.get(scale)` returns `None` -> early `return False`. Covered by `test_unknown_signal_scale_does_not_fire`.
- `threshold is None` (disabled) -> early `return False` regardless of score. Covered by `test_threshold_none_never_fires`.
- No code path in this function can raise for any input shape (bad JSON, wrong type, missing keys, wrong types) — verified by direct inspection, not just tests.

| Requirement | Status | Notes |
|---|---|---|
| Score-keep rule deterministic, no LLM call | Implemented | `score()` returns before reaching the LLM branch in `classify_items()`; proven via `client.calls == 0`. |
| Precedence: score-keep before noise-keyword | Implemented | Confirmed in source (line order) and by the precedence-override test. |
| Defensive read never raises | Implemented | try/except + type guards on every field, confirmed in source. |
| Bool explicitly rejected as score | Implemented | `isinstance(score_value, int) and not isinstance(score_value, bool)`. |
| Opt-in default, `None` disables | Implemented | `filter_hf_keep_upvotes`/`filter_hn_keep_points` default `None` via `_optional_int_env`; `_meets_score_keep_threshold` short-circuits on `None` threshold. |
| `_optional_int_env` fail-safe parsing | Implemented | unset/blank/non-integer/negative -> `None`; valid (incl. `"0"`) -> int. Confirmed in source and 6 dedicated tests. |
| HF collector stamps `signal_score`/`signal_scale="hf_upvotes"`, additive | Implemented | `hf_papers.py`: `{**entry, SIGNAL_SCORE_KEY: upvotes, SIGNAL_SCALE_KEY: SignalScale.HF_UPVOTES}` before `json.dumps`; original `upvotes` key preserved via spread. |
| HN collector stamps `signal_score`/`signal_scale="hn_points"`, additive | Implemented | `hn_algolia.py`: `{**hit, SIGNAL_SCORE_KEY: points, SIGNAL_SCALE_KEY: SignalScale.HN_POINTS}` before `json.dumps`; original `points`/`objectID` preserved via spread. |
| RSS collector untouched | Implemented | No changes to `collection/rss.py` in this diff; RSS items carry neither key, exercised by `test_no_signal_keys_does_not_fire`. |
| Pure `score()` tests, no LLM/I-O | Implemented | `TestScoreKeepRule`/`TestScoreAutoKeep`/`TestScoreNoiseKeywordDrop` build `Item`/`Config` by hand, call `score()` directly, no mocks beyond the injected `_FakeLLMClient` in the `classify_items` test (which is the documented seam). |
| Collector tests use fixtures, no live APIs | Implemented | `_fixture_bytes("hf_daily_papers.json")` / `_fixture_bytes("hn_algolia.json")`, local fixture files, no network calls. |
| Signal key constants extracted and used (Phase 6) | Implemented | `SIGNAL_SCORE_KEY`, `SIGNAL_SCALE_KEY`, and `SignalScale` enum added to `storage/models.py`; used consistently across collectors and filter. |
| `Item.raw` docstring updated | Implemented | `storage/models.py` documents the additive namespaced keys and references the new constant/enum names. |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| Option (a): collectors inject into dict before `json.dumps`, `score()` stays pure/source-agnostic | Yes | Confirmed in both collectors and in `_SCALE_TO_THRESHOLD` mapping (scale-string -> config field lambda), no source-specific branching in `filter.py`. |
| No `Item.score` column, no schema change | Yes | `Item` dataclass fields unchanged except docstring; `raw` stays `str`. |
| No change to collection-time floor thresholds (`hf_min_upvotes`/`hn_min_points`) | Yes | Those fields and their `_int_env` wiring are untouched; new fields use the separate `_optional_int_env` helper. |
| `_optional_int_env` mirrors `_int_env` but returns `None` instead of a default | Yes | Confirmed side-by-side in `config.py`; same fail-safe shape, `None` sentinel instead of caller-provided default. |
| Precedence table (P1 -> score-keep -> noise -> LLM) | Yes | Confirmed in source and by dedicated precedence-override test. |
| Additive raw injection (original keys preserved) | Yes | Both collectors use dict-spread (`{**entry, ...}` / `{**hit, ...}`) rather than replacing the payload. |
| Rollback/migration: None, additive, opt-in, both thresholds default `None` | Yes | `test_unset_defaults_to_none` proves out-of-the-box behavior is unchanged when the env vars are absent. |

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD Evidence reported | Yes | apply-progress contains a "TDD Cycle Evidence" table for all 3 implementation phases. |
| All tasks have tests | Yes | 23/23 original tasks; Phases 1-3 each have explicit RED tasks followed by GREEN/REFACTOR. Phase 6 added pure refactor (0 new behavior/tests). |
| RED confirmed (tests exist) | Yes | All referenced test files (`test_config.py`, `test_hf_papers.py`, `test_hn_algolia.py`, `test_filter.py`) exist and contain the claimed test classes/functions (verified by direct read). |
| GREEN confirmed (tests pass) | Yes | Full suite re-run independently by this verify phase: 177/177 passed, matching the apply-progress claim exactly. |
| Triangulation adequate | Yes | Score-keep rule has 10 distinct `TestScoreKeepRule` cases + 1 `classify_items` integration case covering at/above, precedence, below, disabled, no-keys, per-source independence, malformed, non-int, bool, unknown-scale — no single-case behaviors. |
| Safety Net for modified files | Yes | Pre-existing tests in all 4 modified test files (malformed/empty-payload cases, permalink fallback, etc.) were re-run and remain green — no regressions introduced. |

**TDD Compliance**: 6/6 checks passed

### Assertion Quality
No tautologies, no ghost loops, no assertion-free tests, no ratio problems found. Every new test calls `score()`, `classify_items()`, `parse_hf_papers()`, `parse_hn_algolia()`, or `_optional_int_env()`/`Config.from_env()` directly and asserts a specific expected value (not just `is not None`/`toBeDefined`-style checks). `test_bool_signal_score_does_not_fire` and `test_zero_is_a_valid_value` are notable for asserting non-obvious edge-case values (deliberately using `filter_hf_keep_upvotes=0` to prove `True` is rejected despite `True >= 0`), which is a positive triangulation signal, not a smoke test.

**Assertion quality**: All assertions verify real behavior.

### Issues Found
**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
- **ADDRESSED (Phase 6 post-verify refactor)**: `signal_score` and `signal_scale` string literals were extracted as module-level constants (`SIGNAL_SCORE_KEY`, `SIGNAL_SCALE_KEY`) and a `SignalScale` enum (`HF_UPVOTES`, `HN_POINTS`) in `storage/models.py`, then imported and used consistently across `collection/hf_papers.py`, `collection/hn_algolia.py`, and `synthesis/filter.py` to prevent a future silent typo/scale mismatch. All 177 tests confirm zero behavior change (pure refactor).
- No coverage tool is configured for this project, so "Changed File Coverage" cannot be reported quantitatively; the manual scenario-to-test mapping above stands in as the compliance evidence (test-runtime evidence, not just static reading), per Hard Rule.

### Verdict
PASS
28/28 tasks complete (23 original + 5 Phase 6 refactor), 20/20 spec scenarios have a passing covering test, precedence and defensive-read confirmed by direct source inspection, 177/177 tests pass, ruff clean, zero CRITICAL/WARNING findings — the shared-constants SUGGESTION was fully addressed by the post-verify refactor.
