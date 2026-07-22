# Verification Report: collect-model-flag

**Mode**: Full spec-driven verification (proposal, specs, design, tasks all present) — Strict TDD active.
**Date**: 2026-07-22

## Completeness

| Item | Status |
|---|---|
| Tasks checked | 21/21 (`[x]`), 0 unchecked |
| Spec deltas | `collect-cli` (6 scenarios, 1 requirement), `llm-adapter` (2 scenarios, 1 requirement) |
| Design | Present, decisions traced to code |

## Build / Test / Lint Evidence

- `uv run pytest -q` → **218 passed** (0 failed, 0 skipped)
- `uv run ruff check .` → **All checks passed**
- `git status --short` scope: exactly `src/ai_observatory/cli.py`, `src/ai_observatory/config.py`, `tests/integration/test_collect_integration.py`, `tests/smoke/test_cli.py`, `tests/unit/test_config.py`, `openspec/specs/llm-adapter/spec.md` modified + `openspec/changes/collect-model-flag/` untracked. No scope creep.

## Spec Compliance Matrix

### collect-cli: Model Override Flag

| Scenario | Covering test | Result |
|---|---|---|
| Flag override reaches the client and provenance | `tests/integration/test_collect_integration.py::TestCollectModelProvenance::test_model_flag_is_recorded_in_item_significance` | PASS |
| Env var used when no flag is passed | `tests/smoke/test_cli.py::TestCollectModelFlag::test_env_used_when_no_flag` | PASS |
| Config default used when neither flag nor env is set | `tests/smoke/test_cli.py::TestCollectModelFlag::test_config_default_used_when_neither_set` | PASS |
| Flag takes precedence over env var | `tests/smoke/test_cli.py::TestCollectModelFlag::test_flag_takes_precedence_over_env` | PASS |
| Empty flag value falls back to config default | `tests/smoke/test_cli.py::TestCollectModelFlag::test_empty_flag_falls_back_to_default` | PASS |
| Not-installed model degrades gracefully | Pre-existing: `tests/integration/test_collect_integration.py::TestRunSummary::test_deterministic_only_mode_is_reported` + `tests/unit/test_llm.py` (`LLMModelNotFoundError` on 404) | PASS (unchanged production path, correctly untouched per design's Threat Matrix) |

### llm-adapter: Configuration-Driven Settings (MODIFIED)

| Scenario | Covering test | Result |
|---|---|---|
| Defaults apply when unset (`qwen2.5:7b`) | `tests/unit/test_config.py::TestOllamaSettings::test_no_env_vars_uses_hardcoded_defaults` | PASS |
| Overrides apply when set | `tests/unit/test_config.py::TestOllamaSettings::test_env_overrides_take_effect` | PASS (unchanged, already covered env-override behavior) |

All 8 scenarios across both spec deltas map to a real, currently-passing test. No `UNTESTED`/`FAILING` scenarios.

## Correctness Check (source inspection vs. design)

- `_DEFAULT_OLLAMA_MODEL == "qwen2.5:7b"` in `src/ai_observatory/config.py:18` — confirmed.
- `config.ollama_model` is read at exactly one call site (`Config.from_env()` reading `AIOBS_OLLAMA_MODEL`); `resolved_model = model or config.ollama_model` computed once in `cli.py:102`, consumed once at the sole `OllamaClient(...)` construction (`cli.py:148-150`). No bypass found.
- `--model` implemented as `Annotated[str | None, typer.Option("--model", help=...)] = None` (not the bare `typer.Option(None, ...)` default shown literally in `design.md`'s interface snippet) — documented as Deviation 1 in apply-progress. Verified sound: this is the standard fix for Typer's `OptionInfo`-sentinel-as-default gotcha when a Typer command is also called as a plain Python function (as `test_collect_integration.py` does throughout the suite). CLI-observable behavior is identical; confirmed by the 7 smoke + 13 integration + 1 new provenance test all passing.
- Provenance query scoped to `WHERE model IS NOT NULL` in the new integration test — documented as Deviation 2. Verified sound: `filter.py`'s rule-based (non-LLM) verdicts persist `model = NULL` by existing, unrelated design; the spec's provenance requirement is explicitly scoped to "the run's classified items" (LLM-classified), so excluding NULL rows is the correct assertion target, not a weakening of the check.
- Unrelated `"llama3.2"` literals confirmed untouched: `tests/integration/test_db.py` (2 occurrences), `tests/unit/test_filter.py` (3), `tests/unit/test_llm.py` (6), and `openspec/specs/llm-adapter/spec.md` lines 27/31 (the unrelated "Valid response returns typed result" example scenario). Only `test_config.py:363` and the "Configuration-Driven Settings" requirement/scenario block were changed, exactly as designed.

## Design Coherence

| Design decision | Code match |
|---|---|
| Resolve precedence at call site, not in `Config` | Match — `resolved_model = model or config.ollama_model` in `collect()` |
| No new production seam for testing | Match — tests use existing `monkeypatch.setattr("ai_observatory.cli.OllamaClient", Fake)` seam |
| Bump config default to `qwen2.5:7b` | Match |
| File Changes table (6 files) | Match — identical file set touched, no extras |

## Scope Creep Check

No interactive prompt, no per-source model selection, no model preflight/pull logic added. Changes confined to the 6 files listed in design.md's File Changes table plus the SDD change folder itself. Confirmed via `git status --short`.

## Issues

**CRITICAL**: None.

**WARNING**: None.

**SUGGESTION**: None. Both documented deviations are implementation-detail corrections required to make the design's literal snippet actually work against the existing test-call conventions in this codebase; they change no spec-observable behavior and are transparently logged in apply-progress.

## Verdict

**PASS**

218/218 tests passing, ruff clean, 21/21 tasks complete, 8/8 spec scenarios covered by real passing tests, code matches design with two sound, well-documented deviations, no scope creep.
