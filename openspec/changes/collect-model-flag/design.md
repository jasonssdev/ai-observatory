# Design: `--model` Flag for the `collect` Command

## Technical Approach

Add a single optional Typer option to `collect()` and resolve it against the
existing `Config`. `Config.from_env()` already encodes "env or default" in
`config.ollama_model`, so full 3-level precedence (`--model` > `AIOBS_OLLAMA_MODEL`
> config default) is expressed as one line at the sole `OllamaClient(...)`
construction site (`cli.py:134`). Provenance is untouched: the resolved model
already flows `OllamaClient.model` → `LLMResponse.model` → `Significance.model` →
`item_significance.model`. Separately, per user-approved decision, bump the config
default `_DEFAULT_OLLAMA_MODEL` from `"llama3.2"` (not installed) to `"qwen2.5:7b"`
(installed). This maps to the `collect-cli` "Model Override Flag" delta and the
`llm-adapter` "Configuration-Driven Settings" default update.

## Architecture Decisions

### Decision: Resolve precedence at the call site, not in Config
**Choice**: `resolved_model = model or config.ollama_model` in `collect()`, computed
after `Config.from_env()` and immediately before building `OllamaClient`.
**Alternatives considered**: (a) add a `model` param to `Config.from_env()`;
(b) new resolver helper.
**Rationale**: Config stays a pure env snapshot (frozen dataclass, no CLI coupling).
The `or` idiom gives empty-string fallback for free — `""` is falsy, so `--model ""`
degrades to the default with no hard error. Smallest possible surface; one file.

### Decision: No new production seam for testing
**Choice**: Assert via the existing `monkeypatch.setattr("ai_observatory.cli.OllamaClient", Fake)`
seam. `OllamaClient` is module-imported, so tests already swap it.
**Alternatives considered**: inject a client factory / DI parameter into `collect()`.
**Rationale**: The integration suite already fakes `OllamaClient(url, model, timeout)`
capturing `model` and echoing it into `LLMResponse.model`, so `item_significance.model`
is the true end-to-end provenance assertion. Smoke tests capture the constructor arg
directly. No production indirection needed — keeps the change tiny.

### Decision: Bump the config default to `qwen2.5:7b`
**Choice**: `_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"`.
**Alternatives considered**: keep `llama3.2`; pick `mistral:7b`.
**Rationale**: `llama3.2` is not pulled, so a no-env/no-flag run silently ran
deterministic-only. `qwen2.5:7b` is installed → out-of-box hybrid mode. User-approved.

## Data Flow

    collect(--model?) ──> Config.from_env() ──> resolved = model or config.ollama_model
          │                                              │
          └──> OllamaClient(url, resolved, timeout) ──> generate() ──> LLMResponse.model
                                                                              │
          classify_items ──> Significance(model=...) ──> item_significance.model row

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/cli.py` | Modify | Add `model: str \| None = typer.Option(None, "--model", help=...)`; compute `resolved_model`; pass to `OllamaClient`. |
| `src/ai_observatory/config.py` | Modify | `_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"` (one line). |
| `openspec/specs/llm-adapter/spec.md` | Modify | Update "Configuration-Driven Settings" default `llama3.2` → `qwen2.5:7b` (lines 80, 86). |
| `tests/smoke/test_cli.py` | Modify | Add flag/env/precedence/empty capture cases. |
| `tests/integration/test_collect_integration.py` | Modify | Assert `item_significance.model` end-to-end. |
| `tests/unit/test_config.py` | Modify | Line 363 default assertion `llama3.2` → `qwen2.5:7b`. |

## Interfaces / Contracts

```python
def collect(
    model: str | None = typer.Option(
        None, "--model",
        help="Ollama model for this run. Overrides AIOBS_OLLAMA_MODEL and the "
             "config default. Empty or omitted falls back to the default.",
    ),
) -> None:
    ...
    resolved_model = model or config.ollama_model
    llm_client = OllamaClient(
        config.ollama_url, resolved_model, config.ollama_timeout_seconds
    )
```

**Call-site audit**: `config.ollama_model` is read at exactly one location (`cli.py:135`).
No other consumer bypasses the override.

## Testing Strategy (strict TDD — RED first)

| Layer | Test (maps to spec scenario) | Approach |
|-------|------------------------------|----------|
| Smoke | Flag override reaches client | Fake `OllamaClient`, capture ctor `model`; `--model qwen2.5:3b` → captured `qwen2.5:3b`. |
| Smoke | Env used when no flag | Set `AIOBS_OLLAMA_MODEL`, no flag → captured == env value. |
| Smoke | Config default when neither | Unset env, no flag → captured == `qwen2.5:7b`. |
| Smoke | Flag precedence over env | Env=A, `--model B` → captured B. |
| Smoke | Empty flag falls back | `--model ""`, no env → captured default, exit 0, no error. |
| Integration | Provenance end-to-end | `--model X` → `SELECT DISTINCT model FROM item_significance` == X (via existing `_FakeOllamaClient`). |
| Unit | Config default bump | `test_config.py` no-env → `ollama_model == "qwen2.5:7b"`. |

Behavior-change note: `test_config.py:363` is the only default-assertion needing an
update. Other `"llama3.2"` literals (`test_db.py`, `test_filter.py`, `test_llm.py`,
`llm-adapter` generate scenario) are unrelated fixtures — leave unchanged.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. `--model` is a data value placed
into an existing JSON payload to the Ollama HTTP API; a bad value degrades to
deterministic-only via existing `LLMModelNotFoundError` handling.

## Migration / Rollout

No migration. Flag is additive; omitting it reproduces prior behavior. `data/` is
gitignored — no schema change. The default bump only affects no-env/no-flag runs.

## Open Questions

- None. Both decisions (flag shape, default bump to `qwen2.5:7b`) are user-approved.
