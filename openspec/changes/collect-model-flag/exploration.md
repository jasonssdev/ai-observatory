# Exploration: `--model` flag for `collect` CLI

## Current State
- `collect()` in `src/ai_observatory/cli.py` currently takes NO parameters (line 84).
- Model wiring: `Config.from_env()` (line 88) resolves `config.ollama_model` from
  `AIOBS_OLLAMA_MODEL` env var, falling back to `_DEFAULT_OLLAMA_MODEL="llama3.2"`
  (config.py:18,118). At line 134-136 it builds
  `OllamaClient(config.ollama_url, config.ollama_model, config.ollama_timeout_seconds)`.
- Provenance flow CONFIRMED: `OllamaClient.__init__` stores `model` as `self._model`;
  `generate()` returns `LLMResponse(text, model=self._model, raw)` (llm.py:107).
  `classify_items` writes `Significance(..., model=response.model)` (filter.py:247),
  persisted to `item_significance.model`. So whatever model string is passed to
  `OllamaClient(...)` flows all the way into significance provenance rows automatically.

## Precise Override Point
Line 134-136 of cli.py. The only change needed for propagation is the second positional
arg to `OllamaClient(...)`.

## Precedence Design
Desired: `--model` flag > `AIOBS_OLLAMA_MODEL` env > config default. The env-vs-default
resolution ALREADY happens inside `Config.from_env()` (config.py:118), so
`config.ollama_model` already encodes "env or default". Therefore the CLI only needs:
`resolved_model = model_flag or config.ollama_model`. This single expression satisfies the
full 3-level precedence.

## Affected Areas
- `src/ai_observatory/cli.py` — add `typer.Option` param to `collect()`, resolve
  `model or config.ollama_model`, pass to `OllamaClient(...)`.
- `tests/smoke/test_cli.py` (`TestCollectCommand`) — add CLI test invoking
  `runner.invoke(app, ["collect", "--model", "qwen2.5:7b"])` and asserting the model
  reaches the client / provenance.
- `tests/integration/test_collect_integration.py` — fakes (`_FakeOllamaClient`, etc.)
  already capture `model` via `__init__(url, model, timeout)`; an integration test can
  assert `item_significance.model` equals the override.
- NO change to `src/ai_observatory/config.py` needed (default stays `llama3.2`).

## Approaches
1. **Resolve in cli.py, pass to OllamaClient (RECOMMENDED)** — add
   `model: str | None = typer.Option(None, "--model", help="...")`. Then
   `resolved_model = model or config.ollama_model` and pass `resolved_model`. Pros:
   one-line-ish change; no Config surface change; precedence preserved; provenance flows
   automatically; trivially testable. Cons: resolution lives in CLI not Config (acceptable
   — per-invocation concern). Effort: Low.
2. **Config method (`config.with_model(override)` / `resolve_model()`)** — helper on the
   frozen dataclass. Cons: more surface for a trivial `or`; frozen-dataclass replace
   ceremony; no benefit since env>default already in from_env. Over-engineered. Effort: Medium.

## Recommendation
Approach 1. Because `""` is falsy, `--model ""` naturally falls back to the config default
— acceptable (empty is not a valid model name). Stricter rejection is a separate decision.

## Edge Cases / Risks
- `--model ""`: falsy → falls back to config default. Flag if product wants a hard error.
- Model not installed: existing behavior unchanged. `OllamaClient.generate` raises
  `LLMModelNotFoundError` (404 → llm.py:97-98) on first call; `classify_items` treats any
  `LLMError` as run-level fallback to deterministic-only mode. A bad `--model` degrades
  gracefully, does not crash the unattended run. Good for MVP-3 launchd.
- NO interactive prompt (would break no-TTY launchd scheduling).
- Do NOT change `_DEFAULT_OLLAMA_MODEL` in this change (separate decision). Note: default
  is currently `llama3.2`, not `mistral:7b` as the change brief assumed.

## Ready for Proposal
Yes. Small, well-bounded, single-file production change (cli.py) plus tests. Approach 1.
</content>
</invoke>
