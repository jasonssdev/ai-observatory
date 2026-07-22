# Proposal: `--model` Flag for the `collect` Command

## Intent
Selecting the LLM model for a `collect` run today requires exporting `AIOBS_OLLAMA_MODEL`
before invocation — awkward for ad-hoc model comparison. The user has several pulled models
(qwen2.5:7b, qwen2.5:3b, llama3.1:8b, gemma2:9b, mistral:7b) and needs a fast, per-run way
to pick one without mutating the environment. A `--model` flag makes model choice a
first-class, discoverable CLI concern and records the chosen model in provenance
(`item_significance.model`) for later bake-off analysis.

## Scope

### In Scope
- ADD `model: str | None = typer.Option(None, "--model", help=...)` to `collect()` in
  `src/ai_observatory/cli.py`.
- Resolve `resolved_model = model or config.ollama_model` and pass it as the second
  positional arg to `OllamaClient(config.ollama_url, resolved_model, config.ollama_timeout_seconds)`.
- Preserve existing provenance flow: resolved model → `OllamaClient.model` →
  `LLMResponse.model` → `Significance.model` → `item_significance.model` row.
- Tests (strict TDD): flag override reaches the client / provenance; omitting the flag
  falls back to env then config default; `--model ""` falls back to default.

### Out of Scope (non-goals)
- No interactive model prompt (breaks the no-TTY launchd scheduling planned for MVP-3).
- No per-source model selection, no model validation / preflight installed-check.
- No MVP-3 scheduling work.
- No `_DEFAULT_OLLAMA_MODEL` change in this change's CORE scope (see Open Decision).

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `collect-cli`: ADD a "Model Override Flag" requirement — `--model` sets the run's Ollama
  model with precedence `--model` > `AIOBS_OLLAMA_MODEL` > config default; empty/omitted
  falls back; the resolved model is recorded in significance provenance.

## Approach
Exploration **Approach 1**. `Config.from_env()` already encodes "env or default" in
`config.ollama_model`, so a single `model or config.ollama_model` expression at the
`OllamaClient(...)` construction site satisfies the full 3-level precedence with no Config
surface change. Because `""` is falsy, `--model ""` gracefully falls back to the default
(empty is not a valid model name — no hard error). A model that is not installed keeps
existing behavior: `OllamaClient.generate` raises `LLMModelNotFoundError`, `classify_items`
degrades the run to deterministic-only mode — no crash, safe for unattended runs.

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/cli.py` | Modified | `--model` option on `collect()`; resolve and pass to `OllamaClient`. |
| `tests/smoke/test_cli.py` | Modified | CLI override / fallback / empty-string cases. |
| `tests/integration/test_collect_integration.py` | Modified | Assert `item_significance.model` equals the override end-to-end. |
| `openspec/specs/collect-cli/spec.md` | Modified | New "Model Override Flag" requirement + scenarios. |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Typo'd `--model` value silently degrades to deterministic-only | Med | Documented behavior; end-of-run summary already reports filter mode; no data corruption. |
| `--model ""` fallback surprises a user expecting an error | Low | Documented in help text and spec; graceful-fallback is the chosen contract. |

## Open Decision (NOT included by default — user's call)
`_DEFAULT_OLLAMA_MODEL` in `config.py` is still `"llama3.2"`, which is NOT installed, so a
run with no env var and no flag silently falls to deterministic-only. Optionally bump the
default to an installed model (e.g. `mistral:7b`, already validated). The user just pulled
qwen2.5:7b/3b, llama3.1:8b, gemma2:9b and may prefer a different default after a bake-off.
Flagged for confirmation; NOT part of this proposal's core scope.

## Rollback Plan
Single-file production change plus tests; revert the change branch. No schema change, no
data migration (`data/` is gitignored). The flag is additive — omitting it reproduces
today's env>default behavior exactly.

## Dependencies
None new. Reuses `Config`, `OllamaClient`, and the existing significance provenance path.

## Success Criteria
- [ ] `collect --model X` passes `X` to `OllamaClient` and records it in `item_significance.model`.
- [ ] Omitting `--model` falls back to `AIOBS_OLLAMA_MODEL`, then to the config default.
- [ ] `--model ""` falls back to the config default without error.
- [ ] A not-installed model degrades to deterministic-only, no crash.
- [ ] `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 400 changed lines)
Estimate ~50-90 changed lines: cli.py delta (~5-10), smoke tests (~25-40), integration
test (~15-30), spec delta (~15-25). Small, single-PR slice. `400-line budget risk: Low`.
`Chained PRs recommended: No`. `Decision needed before apply: Yes` — confirm whether to
also bump `_DEFAULT_OLLAMA_MODEL` (Open Decision), otherwise it stays out of scope.
</content>
