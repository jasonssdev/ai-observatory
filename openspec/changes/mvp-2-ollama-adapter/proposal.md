# Proposal: MVP-2 Ollama Local-LLM Adapter

## Intent

First MVP-2 slice per `docs/roadmap.md`: a thin, resilient local-LLM adapter over a
local Ollama HTTP server, exposing a typed port the later hybrid daily filter will
consume. Fills the `synthesis/llm.py` slot prescribed in `docs/architecture.md`
(line 60-63) — "LLM client abstraction (local or API)". Local-only is a hard
constraint: the model never leaves the machine, no LLM API key. This slice ships
prompt-in / typed-response-out only; classification logic is a later slice.

## Scope

### In Scope
- New package `src/ai_observatory/synthesis/` (`__init__.py` + `llm.py`).
- `OllamaClient` adapter: sync `httpx` over `POST /api/generate`, `stream: false`, optional-injected `httpx.Client` (mirrors mvp-1 `HttpxFetcher` seam), explicit `httpx.Timeout`.
- Typed contract: `LLMClient` Protocol port, frozen `LLMResponse(text, model, raw)`, `LLMError` hierarchy.
- `config.py`: add `ollama_url`, `ollama_model`, `ollama_timeout_seconds` + `AIOBS_OLLAMA_*` wiring + new `_float_env()` helper.
- Tests: success, server-unreachable, timeout, model-not-found, malformed-response (all via `httpx.MockTransport`, zero network) + config env-var table tests.

### Out of Scope (non-goals)
- Hybrid filter / classification logic (next slice).
- JSON/schema-structured output (`format`), system prompt, `/api/chat`.
- Source expansion (HF Daily Papers, HN Algolia, P2 feeds).
- Retry/backoff (deferred to v1.0 per roadmap), streaming, async.
- No `cli.py` command, no `synthesis/daily.py`, no `sources.yaml` change.

## Capabilities

### New Capabilities
- `llm-adapter`: local Ollama HTTP adapter exposing a typed `generate(prompt) -> LLMResponse` port; surfaces failures as a typed `LLMError` hierarchy (unavailable / timeout / model-not-found / malformed).

### Modified Capabilities
None. (`config.py` gains fields but no existing capability's spec-level behavior changes; env-config remains the mvp-1 pattern.)

## Approach

Exploration **Approach 1**: sync `httpx` over `/api/generate`, `stream:false`, mapping
httpx/json failures to `LLMError`. Reuses the exact mvp-1 injectable-client seam →
fully strict-TDD-able with `MockTransport`. Port + typed errors + adapter co-located
in `synthesis/llm.py`. Contract:

```python
@dataclass(frozen=True)
class LLMResponse:
    text: str; model: str; raw: str

class LLMClient(Protocol):
    def generate(self, prompt: str) -> LLMResponse: ...

class OllamaClient:  # adapter
    def __init__(self, url, model, timeout, client: httpx.Client | None = None): ...
```

### Key Decisions (resolves 8 open items)
| # | Decision |
|---|----------|
| 1 | **Endpoint**: `/api/generate` (`stream:false`), completion read from `response`. `/api/chat` deferred — system-role separation is the filter slice's concern. |
| 2 | **Failure shape**: typed exception hierarchy, NOT swallow-and-return-empty like `RssCollector`. Rationale: the hybrid filter must know whether classification happened, to fall back to deterministic-only rules. `LLMError` base + `LLMUnavailableError`, `LLMTimeoutError`, `LLMModelNotFoundError`, `LLMResponseError`. |
| 3 | **Default model**: `AIOBS_OLLAMA_MODEL` defaults to `llama3.2` (overridable). Defaulted, not required — keeps `from_env()` total, matching mvp-1. |
| 4 | **Timeout**: `AIOBS_OLLAMA_TIMEOUT_SECONDS` default `60.0` (generation is slow, not the feed's 10s). Add `_float_env()` alongside `_int_env()`, same fail-safe-on-missing/invalid/negative contract. |
| 5 | **Module layout**: single `synthesis/llm.py` (port + errors + adapter) for one backend now; split to `synthesis/base.py` only if a second backend appears. |
| 6 | **Client lifecycle**: per-call `with httpx.Client(timeout=...)` when none injected (mirrors `HttpxFetcher`); injected client used directly (test seam). |
| 7 | **Retry/backoff**: OUT — deferred to v1.0 per roadmap hardening. |
| 8 | **`format`/`options` pass-through**: OUT this slice — strictly prompt-in / text-out. Added when the filter needs structured output. |

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/__init__.py` | New | New package. |
| `src/ai_observatory/synthesis/llm.py` | New | Port, `LLMResponse`, `LLMError` hierarchy, `OllamaClient`. |
| `src/ai_observatory/config.py` | Modified | 3 `AIOBS_OLLAMA_*` fields + `_float_env()`. |
| `tests/unit/test_llm.py` | New | 5 mandatory cases via `MockTransport`. |
| `tests/unit/test_config.py` | Modified | env-var table tests for 3 new settings. |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Wrong failure-mode classification (Connect vs Timeout vs 404 vs JSONDecode) | Med | Each maps to a dedicated `LLMError`; all 5 cases mandatory-tested. |
| Model-not-found detection relies on Ollama 404 + error body | Med | Assert against a canned 404 body via `MockTransport`; never live Ollama. |
| Timeout too small → false `LLMTimeoutError` | Low | Generous 60s default; env-overridable. |
| Scope creep into filter/JSON-output | Med | Explicit non-goals; adapter stays prompt-in/typed-out. |

## Rollback Plan
New feature slice; no existing behavior depends on it. `synthesis/` is a new package
and the 3 config fields are additive with defaults, so `from_env()` stays valid if
unused. Revert the change branch; no migrations, no data, no entry-point change.

## Dependencies
None new. Reuse `httpx` + stdlib `json`. Runtime prerequisite (not a code dep): a
local Ollama server with the target model pulled — only needed for integration/smoke,
never for unit tests.

## Success Criteria
- [ ] `OllamaClient(...).generate(prompt)` returns `LLMResponse(text, model, raw)` on a mocked 200.
- [ ] Server-unreachable → `LLMUnavailableError`; timeout → `LLMTimeoutError`.
- [ ] 404 + model-not-found body → `LLMModelNotFoundError`; malformed/non-JSON → `LLMResponseError`.
- [ ] `AIOBS_OLLAMA_*` env vars resolve via `from_env()` with correct defaults (incl. `_float_env()` fail-safe).
- [ ] All tests use `httpx.MockTransport` (zero network); `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 800 changed lines)
Estimate ~300-380 changed lines: `llm.py` (~120-150), `config.py` delta (~25), `test_llm.py` (~130-160), `test_config.py` delta (~30), `__init__.py` (~2). Comfortably one PR under the 800-line budget. `400-line budget risk: Low`. `Chained PRs recommended: No`.
