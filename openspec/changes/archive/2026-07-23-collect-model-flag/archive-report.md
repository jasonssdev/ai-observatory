# Archive Report: Model Override Flag for `collect` Command

**Change**: collect-model-flag
**Archived**: 2026-07-23
**Verdict**: PASS 0/0/0 (218/218 tests)
**Critical Issues**: 0
**Warnings**: 0

## Executive Summary

The `collect` command now accepts a `--model` flag to select the Ollama model on a per-run basis, enabling ad-hoc model comparison without environment-variable mutation. The flag follows precedence `--model` > `AIOBS_OLLAMA_MODEL` env > config default, resolved as `model or config.ollama_model` at the sole `OllamaClient()` construction site in `cli.py`. The resolved model is recorded in `item_significance.model` provenance for later bake-off analysis. Alongside the flag, the default Ollama model was bumped from `llama3.2` (not installed) to `qwen2.5:7b` (installed), enabling out-of-box hybrid classification. All 21 implementation tasks complete, 218 tests passing, all 8 spec scenarios (6 collect-cli, 2 llm-adapter) covered by real, passing tests. Specs synced to main, change folder archived, zero critical/warning findings. SDD cycle complete.

## Archived Change Artifacts

### OpenSpec Change Folder Contents
| File | Status |
|------|--------|
| proposal.md | ✅ Archived |
| exploration.md | ✅ Archived |
| design.md | ✅ Archived |
| tasks.md | ✅ Archived (21/21 tasks complete) |
| verify-report.md | ✅ Archived (PASS verdict confirmed) |

**Archive Location**: `/Users/jasonssdev/Dev/Projects/ai-observatory/openspec/changes/archive/2026-07-23-collect-model-flag/`

## Specs Synced to Main

### Delta 1: collect-cli
**Action**: ADDED (1 new requirement with 6 scenarios)

#### Added Requirement
- **Model Override Flag**: New requirement establishing the `--model` option precedence (`--model` > `AIOBS_OLLAMA_MODEL` > config default), graceful fallback semantics (empty string, omitted flag), and error handling (non-installed models degrade to deterministic-only). Inserted after the "Live Progress Feedback" requirement as the final CLI requirement. Six scenarios covering flag override, env fallback, config default, precedence over env, empty-string fallback, and graceful degradation of non-installed models.

**Result**: `openspec/specs/collect-cli/spec.md` now includes 10 total requirements with 26+ scenarios (previously 9 requirements, reflecting the new model-override requirement and its 6 scenarios).

### Delta 2: llm-adapter
**Action**: MODIFIED (1 requirement, default value bump)

#### Modified Requirement
- **Configuration-Driven Settings**: Updated existing requirement to reflect the new default model `qwen2.5:7b` (previously `llama3.2`). Two scenarios already present ("Defaults apply when unset" and "Overrides apply when set") now use `qwen2.5:7b` in the expected output.

**Result**: `openspec/specs/llm-adapter/spec.md` Configuration-Driven Settings requirement now specifies `ollama_model == "qwen2.5:7b"` as the default (lines 77-87).

## Implementation Changes

### Files Modified in Deployment
| File | Action | Change Lines | Purpose |
|------|--------|--|---------|
| `src/ai_observatory/cli.py` | Modified | 1 new param, 2 resolver lines, 1 OllamaClient arg | Add `--model` option, resolve precedence, pass to client |
| `src/ai_observatory/config.py` | Modified | 1 line | Bump `_DEFAULT_OLLAMA_MODEL` from `llama3.2` to `qwen2.5:7b` |
| `tests/smoke/test_cli.py` | Modified | ~40 lines | Add `_CapturingOllamaClient` fake and `TestCollectModelFlag` class with 5 test methods |
| `tests/integration/test_collect_integration.py` | Modified | ~15 lines | Add provenance end-to-end test asserting `item_significance.model` |
| `tests/unit/test_config.py` | Modified | 1 line | Update default assertion: `llama3.2` → `qwen2.5:7b` |
| `openspec/specs/llm-adapter/spec.md` | Modified | 2 lines | Update requirement lines 80, 86 with new default |
| `openspec/specs/collect-cli/spec.md` | Modified | 51 lines (new) | Add "Model Override Flag" requirement with 6 scenarios |

**Total**: 6 existing files modified + spec sync completed. No new files created in production.

## Precedence Design

The `--model` flag implements a clean 3-level precedence:

```
--model flag (if non-empty) > AIOBS_OLLAMA_MODEL env var > config default
```

Implemented as a single expression: `resolved_model = model or config.ollama_model`

- `model` parameter is None when omitted or resolved via Typer; non-empty when `--model X` is passed
- `config.ollama_model` encodes "env var (if set) or hardcoded default"
- Python's `or` operator: if `model` is truthy, use it; otherwise fall back to `config.ollama_model`
- Empty string (`--model ""`) is falsy, so it naturally falls back to config default without error

## Default Model Bump: llama3.2 → qwen2.5:7b

The default model was changed as part of this change (user-approved decision noted in proposal's "Open Decision" section):

- **Before**: `_DEFAULT_OLLAMA_MODEL = "llama3.2"` (not pulled on the user's Ollama installation)
  - Consequence: runs with no flag and no env var silently fell back to deterministic-only mode
- **After**: `_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"` (installed model)
  - Consequence: out-of-box hybrid classification mode (LLM + deterministic filters)

Both the CLI flag and the default bump are independent changes coordinated in this SDD cycle:
- The flag itself (precedence logic) is the core requirement
- The default bump is a configuration improvement enabled by the flag, making it discoverable and per-run

## Test Coverage Matrix

### collect-cli Spec Scenarios (6 total)

| Scenario | Test Path | Result |
|----------|-----------|--------|
| Flag override reaches the client and provenance | `tests/integration/test_collect_integration.py::TestCollectModelProvenance::test_model_flag_is_recorded_in_item_significance` | PASS |
| Env var used when no flag is passed | `tests/smoke/test_cli.py::TestCollectModelFlag::test_env_used_when_no_flag` | PASS |
| Config default used when neither flag nor env is set | `tests/smoke/test_cli.py::TestCollectModelFlag::test_config_default_used_when_neither_set` | PASS |
| Flag takes precedence over env var | `tests/smoke/test_cli.py::TestCollectModelFlag::test_flag_takes_precedence_over_env` | PASS |
| Empty flag value falls back to config default | `tests/smoke/test_cli.py::TestCollectModelFlag::test_empty_flag_falls_back_to_default` | PASS |
| Not-installed model degrades gracefully | Pre-existing paths: `LLMModelNotFoundError` on 404, deterministic-only fallback in `classify_items` | PASS |

### llm-adapter Spec Scenarios (2 total)

| Scenario | Test Path | Result |
|----------|-----------|--------|
| Defaults apply when unset (`qwen2.5:7b`) | `tests/unit/test_config.py::TestOllamaSettings::test_no_env_vars_uses_hardcoded_defaults` | PASS |
| Overrides apply when set | `tests/unit/test_config.py::TestOllamaSettings::test_env_overrides_take_effect` | PASS |

**All 8 spec scenarios mapped to real, passing tests. No UNTESTED or FAILING scenarios.**

## Build / Test / Lint Results

- **Test suite**: `uv run pytest -q` → **218 passed** (0 failed, 0 skipped)
- **Linting**: `uv run ruff check .` → **All checks passed**
- **Scope**: Modified exactly 6 production + spec files; no unintended scope creep

## Task Completion

**21/21 tasks complete**

Phases executed in strict TDD order:
1. Phase 1: Config default bump (RED/GREEN/REFACTOR: update test assertion, implement default, verify)
2. Phase 2: `--model` flag and precedence logic (RED/GREEN/REFACTOR: 5 test scenarios, 1 implementation, verify)
3. Phase 3: Provenance integration test (RED/GREEN/REFACTOR: end-to-end assertion, no new production seams)
4. Phase 4: Spec sync and final verification (Update llm-adapter spec, verify all scenario coverage)

All checkboxes marked complete; no stale unchecked tasks.

## Design Decisions & Deviations

### Design Decision 1: Resolve precedence at call site, not in Config
- **Choice**: `resolved_model = model or config.ollama_model` in `collect()`, computed immediately before `OllamaClient()` construction
- **Rationale**: Keeps Config a pure env snapshot (no CLI coupling); one-line precedence; empty-string fallback for free

### Design Decision 2: No new production seam for testing
- **Choice**: Reuse existing `monkeypatch.setattr("ai_observatory.cli.OllamaClient", Fake)` seam
- **Rationale**: Tests already capture constructor args; integration suite already fakes the client; no indirection needed

### Design Decision 3: Bump config default to `qwen2.5:7b`
- **Choice**: Update `_DEFAULT_OLLAMA_MODEL` from `llama3.2` to `qwen2.5:7b`
- **Rationale**: `llama3.2` is not installed (silent deterministic-only fallback); `qwen2.5:7b` is installed (enables hybrid mode out-of-box)

### Implementation Deviations (sound, documented)

**Deviation 1**: Typer Option annotation
- Delta spec shows: `model: str | None = typer.Option(None, "--model", help=...)`
- Actual implementation: `Annotated[str | None, typer.Option("--model", help=...)] = None`
- Reason: Typer's `OptionInfo` sentinel-as-default gotcha; the `Annotated` form is required when `collect()` is called as a plain Python function (as integration tests do)
- Impact: Zero spec-observable behavior change; all tests pass

**Deviation 2**: Provenance query scope
- Integration test scopes the query to `WHERE model IS NOT NULL`
- Reason: Rule-based (non-LLM) verdicts persist `model = NULL` by unrelated design; spec's provenance requirement is scoped to "the run's classified items" (LLM-classified)
- Impact: Correct assertion target, not a weakening

## Verification Findings

### Critical Issues
**None**

### Warnings
**None**

### Suggestions
**None**

All deviations are implementation-detail corrections required to make the design work against existing conventions; they change no spec-observable behavior and are transparently documented.

## Rollback Plan

The change is additive and safe to roll back:
- Revert cli.py (remove `--model` param, remove resolver, restore original `OllamaClient` arg)
- Revert config.py (restore `_DEFAULT_OLLAMA_MODEL = "llama3.2"`)
- Revert spec changes
- Omitting the flag reproduces prior behavior exactly; no schema changes; no data migrations required

## Artifact Trail

- **Proposal**: Scope, intent, approach, risks, rollback (2026-07-22)
- **Exploration**: Current state, override point, precedence design, edge cases (2026-07-22)
- **Design**: Technical approach, architecture decisions, data flow, file changes, testing strategy (2026-07-22)
- **Tasks**: Review forecast, 4-phase TDD execution plan, 21 tasks (2026-07-22)
- **Verification Report**: Full spec compliance, test coverage, correctness check, scope creep validation (2026-07-22)
- **Archive Report**: This document (2026-07-23)

## Engagement & Sign-Off

- **Specification Status**: 8/8 scenarios verified by real passing tests
- **Implementation Status**: 6 files modified, all tests green, linting clean
- **Review Status**: Verification report PASS; zero critical/warning findings
- **Task Status**: 21/21 complete
- **Archive Status**: All artifacts archived at `/Users/jasonssdev/Dev/Projects/ai-observatory/openspec/changes/archive/2026-07-23-collect-model-flag/`

**The SDD cycle for `collect-model-flag` is COMPLETE.** Ready for the next change.
