# Tasks: `--model` Flag for the `collect` Command

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~150-200 |
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
| 1 | `--model` Typer option + precedence resolution in `collect()`, config default bump, full test coverage | PR 1 (only) | `uv run pytest tests/smoke/test_cli.py tests/integration/test_collect_integration.py tests/unit/test_config.py -q` | `uv run pytest tests/integration/test_collect_integration.py -q` — exercises full `collect()` pipeline with fake `OllamaClient`, real SQLite `item_significance` provenance check | Revert `cli.py`/`config.py` diff; omitting `--model` reproduces prior behavior exactly |

## Phase 1: Config Default (Foundation)

- [x] 1.1 RED — `tests/unit/test_config.py:363` — update `test_no_env_vars_uses_hardcoded_defaults` assertion from `assert config.ollama_model == "llama3.2"` to `assert config.ollama_model == "qwen2.5:7b"` (fails against current default).
- [x] 1.2 GREEN — `src/ai_observatory/config.py:18` — change `_DEFAULT_OLLAMA_MODEL = "llama3.2"` to `_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"`.
- [x] 1.3 REFACTOR — `uv run pytest tests/unit/test_config.py -q` + `uv run ruff check src/ai_observatory/config.py`.

## Phase 2: `--model` Flag and Precedence

- [x] 2.1 RED — `tests/smoke/test_cli.py`: add `_CapturingOllamaClient` fake (mirrors `_FakeOllamaClient` from `test_collect_integration.py`: `__init__(self, url, model, timeout)` capturing `model` on the class, `generate()` returns a minimal `SIGNIFICANT` `LLMResponse`); add `TestCollectModelFlag` class.
- [x] 2.2 RED — `TestCollectModelFlag.test_flag_overrides_default`: `monkeypatch.setattr(cli_module, "OllamaClient", _CapturingOllamaClient)`, invoke `runner.invoke(app, ["collect", "--model", "qwen2.5:3b"])` (no env set) → assert captured `model == "qwen2.5:3b"` and `exit_code == 0` (spec: Flag override reaches the client).
- [x] 2.3 RED — `test_env_used_when_no_flag`: `monkeypatch.setenv("AIOBS_OLLAMA_MODEL", "mistral")`, invoke without `--model` → captured `model == "mistral"` (spec: Env var used when no flag).
- [x] 2.4 RED — `test_config_default_used_when_neither_set`: no `--model`, no env → captured `model == "qwen2.5:7b"` (spec: Config default used).
- [x] 2.5 RED — `test_flag_takes_precedence_over_env`: `AIOBS_OLLAMA_MODEL="mistral"` + `--model qwen2.5:3b` → captured `model == "qwen2.5:3b"` (spec: Flag precedence over env).
- [x] 2.6 RED — `test_empty_flag_falls_back_to_default`: `--model ""`, no env → `exit_code == 0`, no exception, captured `model == "qwen2.5:7b"` (spec: Empty flag value falls back).
- [x] 2.7 GREEN — `src/ai_observatory/cli.py`: add `model` parameter to `collect()` (implemented via `Annotated[str | None, typer.Option("--model", help=...)] = None` instead of the bare `= typer.Option(None, ...)` form — see Deviations).
- [x] 2.8 GREEN — `src/ai_observatory/cli.py:88` (after `config = Config.from_env()`): add `resolved_model = model or config.ollama_model`.
- [x] 2.9 GREEN — `src/ai_observatory/cli.py:134-136`: change `OllamaClient(config.ollama_url, config.ollama_model, config.ollama_timeout_seconds)` to `OllamaClient(config.ollama_url, resolved_model, config.ollama_timeout_seconds)`.
- [x] 2.10 REFACTOR — `uv run pytest tests/smoke/test_cli.py -q` + `uv run ruff check src/ai_observatory/cli.py`.

## Phase 3: Provenance Integration Test

- [x] 3.1 RED — `tests/integration/test_collect_integration.py`: add a test in a new/existing class that calls `collect(model="qwen2.5:3b")` directly (matching the file's existing direct-call style) with `_FakeOllamaClient` patched via `monkeypatch.setattr("ai_observatory.cli.OllamaClient", _FakeOllamaClient)`, then `SELECT DISTINCT model FROM item_significance` on the resulting DB → assert the LLM-classified distinct value is `"qwen2.5:3b"` (spec: Flag override reaches the client and provenance; query filters `WHERE model IS NOT NULL` since rule-based verdicts persist `model = NULL` — see Deviations).
- [x] 3.2 GREEN — confirmed the direct `collect(model=...)` call itself required the `Annotated` fix (see Deviations); no further wiring changes needed beyond Phase 2.
- [x] 3.3 REFACTOR — `uv run pytest tests/integration/test_collect_integration.py -q`.

## Phase 4: Spec Sync and Final Verification

- [x] 4.1 Update `openspec/specs/llm-adapter/spec.md` (lines ~80, 86 per design) — replace `llama3.2` default with `qwen2.5:7b` in the deployed "Configuration-Driven Settings" requirement to match the delta.
- [x] 4.2 Grep for remaining `"llama3.2"` literals outside `test_config.py:363`; confirmed `test_db.py`, `test_filter.py`, `test_llm.py`, and the `llm-adapter` generate-scenario fixtures (lines 27/31) are unrelated and left unchanged (per design's behavior-change note).
- [x] 4.3 `uv run pytest` — full suite green, no regressions (218 passed).
- [x] 4.4 `uv run ruff check .` — clean.
- [x] 4.5 Cross-check all 6 `collect-cli` spec-delta scenarios and both `llm-adapter` scenarios against an executed test case (see Apply Progress evidence table).
