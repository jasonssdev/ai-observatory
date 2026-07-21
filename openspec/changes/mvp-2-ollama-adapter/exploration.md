# Exploration: MVP-2 slice 1 — Ollama local-LLM adapter (`llm.py`)

First slice of MVP-2 per `docs/roadmap.md`: a thin, resilient local-LLM adapter over a
local Ollama HTTP server, exposing a typed port the later hybrid daily filter will
consume. Grounded in roadmap.md, architecture.md, AGENTS.md, the current scaffold,
pyproject.toml, and the archived mvp-1-daily-collector change.

## Current State (scaffold reality)
- Package `src/ai_observatory/` with `collection/` (base.py, rss.py, sources.py, dedup.py, text.py), `storage/` (models.py, db.py, records.py), `config.py`, `cli.py`. No `synthesis/` package yet, no `llm.py`.
- `docs/architecture.md` (line 60-63) prescribes the target layout: `synthesis/{daily.py, weekly.py, llm.py}`. `llm.py` = "LLM client abstraction (local or API)". Local-only via Ollama is a hard constraint (architecture lines 148-166, 193): the model never leaves the machine; there is NO LLM API key; external APIs are only ever for *fetching sources*.
- Deps already present: `httpx>=0.28.1`, `feedparser`, `pyyaml`, `typer`. Dev: `pytest>=9.1.1`, `ruff>=0.15.22`. Python >=3.13. NO new runtime dep needed — reuse `httpx` + stdlib `json`. (Do NOT add the `ollama` python SDK; httpx keeps the seam testable and consistent with RSS.)
- Established hexagonal pattern (mvp-1): a Protocol port in `collection/base.py` (`Fetcher`, `Collector`) + concrete adapter in `rss.py` (`HttpxFetcher`, `RssCollector`). Adapter takes an OPTIONAL injected `httpx.Client`; when present it is used directly (tests inject `httpx.Client(transport=httpx.MockTransport(handler))`), else a client is created per-call inside a `with` block. Explicit `httpx.Timeout(connect/read/write/pool)`. Frozen dataclasses for models. Zero network in tests.
- Config pattern (`config.py`): frozen `Config` dataclass, `from_env()` classmethod, `AIOBS_*` env vars with hardcoded defaults, `_int_env()` helper that fails safe on missing/invalid/negative. There is NO float helper yet.
- Test layout: `tests/{unit,integration,smoke}/`. Env-var behavior table-tested with `monkeypatch` (see test_config.py). httpx behavior tested via `MockTransport` handlers (see test_rss.py `TestHttpxFetcher`).

## Key divergence from RSS pattern (important)
RssCollector SWALLOWS per-source failures (log + return `[]`) for per-source isolation. The LLM adapter should NOT silently swallow: the future hybrid filter must know whether classification actually happened (to fall back to deterministic-only). So failure semantics differ — surface failures as TYPED errors (or a typed result), not empty returns. This is the central design decision for the proposal.

## Affected Areas
- `src/ai_observatory/synthesis/__init__.py` — NEW package (does not exist).
- `src/ai_observatory/synthesis/llm.py` — NEW. Ollama adapter + typed port (Protocol, response dataclass, error types).
- `src/ai_observatory/config.py` — MODIFY. Add `ollama_url`, `ollama_model`, `ollama_timeout_seconds` fields + `AIOBS_OLLAMA_*` env wiring; likely add a `_float_env()` helper (timeout is float).
- `tests/unit/test_llm.py` — NEW. success, server-unreachable, timeout, malformed-response, model-not-found.
- `tests/unit/test_config.py` — MODIFY. env-var table tests for the 3 new settings.
- NOT touched this slice: `cli.py` (no new command — filter slice wires it later), `synthesis/daily.py` (separate slice), no `sources.yaml` change.

## Ollama HTTP surface (design ground truth)
- Default endpoint `http://localhost:11434`.
- `POST /api/generate` (single prompt): body `{"model": "...", "prompt": "...", "stream": false}`. With `stream:false` returns ONE JSON object: `{"model","created_at","response":"<text>","done":true, ...}`. The completion text is under `response`.
- `POST /api/chat` (role messages): body `{"model","messages":[{"role":"user","content":"..."}],"stream":false}` → `{"message":{"role":"assistant","content":"<text>"},"done":true}`. Text under `message.content`. `chat` allows a separate `system` role (useful later for a classification system prompt).
- `format: "json"` (or a JSON schema) forces structured output — belongs to the FILTER slice, keep this adapter thin/format-agnostic (optionally a pass-through param, but recommend deferring).
- Failure modes over HTTP:
  - Server down/unreachable → `httpx.ConnectError` (connection refused).
  - Timeout → `httpx.TimeoutException` / `httpx.ReadTimeout` (generation is slow — use a generous timeout, ~60s, not the feed's 10s).
  - Model not found → HTTP 404 with body `{"error":"model '...' not found, try pulling it first"}` → `raise_for_status()` raises `httpx.HTTPStatusError` (inspect status/body to classify).
  - Malformed / non-JSON body → `response.json()` raises `json.JSONDecodeError`; or valid JSON missing the expected key.

## Where it lives + typed contract
Follow architecture.md exactly: `src/ai_observatory/synthesis/llm.py` (create `synthesis/__init__.py`), NOT a top-level `llm/` package. Proposed contract:
```python
@dataclass(frozen=True)
class LLMResponse:
    text: str        # the completion (response / message.content)
    model: str
    raw: str         # json.dumps of the full Ollama payload, for traceability

class LLMClient(Protocol):          # the PORT the filter depends on
    def generate(self, prompt: str) -> LLMResponse: ...

class LLMError(Exception): ...              # base
class LLMUnavailableError(LLMError): ...    # server down/unreachable
class LLMTimeoutError(LLMError): ...        # request timed out
class LLMModelNotFoundError(LLMError): ...  # 404 / model missing
class LLMResponseError(LLMError): ...       # malformed / non-JSON / missing key

class OllamaClient:                 # the ADAPTER
    def __init__(self, url, model, timeout, client: httpx.Client | None = None): ...
    def generate(self, prompt: str) -> LLMResponse: ...
```
Config additions: `AIOBS_OLLAMA_URL` (default `http://localhost:11434`), `AIOBS_OLLAMA_MODEL` (default TBD, e.g. `llama3.2` — decision), `AIOBS_OLLAMA_TIMEOUT_SECONDS` (default ~60, float).

## Approaches
1. **httpx sync + `/api/generate`, non-streaming, typed exceptions (RECOMMENDED)** — mirror `HttpxFetcher`: optional injected `httpx.Client`, per-phase `httpx.Timeout`, `stream:false`, map httpx/json failures to the `LLMError` hierarchy.
   - Pros: reuses existing dep + exact mvp-1 seam; fully TDD-able with `MockTransport` (zero network); simplest Ollama endpoint; explicit failure typing lets the filter fall back cleanly; sync matches the rest of the codebase.
   - Cons: adapter+port in one file (slight coupling); `/api/generate` lacks system-role separation the filter may later want.
   - Effort: Low-Medium.
2. **`/api/chat` instead of `/api/generate`** — same infra, chat endpoint for system+user role separation.
   - Pros: better fit for a future classification system prompt; more forward-looking.
   - Cons: marginally more request/response shape to model now for a benefit the filter slice owns; slightly heavier response nesting.
   - Effort: Low-Medium.
3. **`ollama` python SDK** — use the official client library.
   - Pros: less HTTP boilerplate.
   - Cons: NEW dependency; hides the seam (harder to inject a mock transport → fights strict TDD); inconsistent with the httpx-everywhere convention. Rejected.
4. **Swallow errors like RssCollector (return empty/None)** — Rejected: hides LLM availability from the filter, which needs it for deterministic fallback.
5. **async httpx** — Rejected for this slice: whole codebase is sync; async adds no value for a single sequential call and complicates tests.

## Recommendation
Approach 1: sync httpx over `/api/generate`, `stream:false`, optional-injected client mirroring `HttpxFetcher`, port + typed `LLMError` hierarchy in `synthesis/llm.py`, config via `AIOBS_OLLAMA_*`. Keep the adapter thin and format-agnostic; `json`/schema output and the system prompt are the filter slice's concern. Defer retry/backoff to v1.0 (roadmap explicitly parks hardening/retries there). Reconsider `/api/chat` only if the proposal decides the system-prompt separation is worth pulling forward.

## Open Questions / Decisions for the proposal
1. `/api/generate` vs `/api/chat` (system-role separation now vs later).
2. Error handling shape: typed exception hierarchy (recommended) vs a typed result/`Result`-style return.
3. Default model name for `AIOBS_OLLAMA_MODEL` (and whether it is required vs defaulted).
4. Timeout default + whether to add a `_float_env()` helper (timeout is fractional) or reuse int seconds.
5. Port + adapter in one `synthesis/llm.py` vs a `synthesis/base.py` (port) + `llm.py` (adapter) split like `collection/base.py`+`rss.py`. Recommend single file for one backend now.
6. Adapter lifecycle: create per-call `with httpx.Client(...)` when no client injected (mirror HttpxFetcher) — confirm.
7. Retry/backoff explicitly OUT (defer to v1.0) — confirm.
8. Whether `generate` accepts an optional `format`/`options` pass-through now or stays strictly prompt-in/text-out.

## Risks
- Failure-mode classification correctness: `httpx.ConnectError` vs `TimeoutException` vs `HTTPStatusError(404)` vs `JSONDecodeError` must each map to the right `LLMError`; the malformed-response and unreachable/timeout tests are mandatory (AGENTS.md testing discipline).
- Model-not-found detection depends on Ollama's 404 + error-body contract; assert against a canned 404 body, do not rely on live Ollama.
- Timeout tuning: LLM generation is far slower than feed fetch — a too-small timeout produces false `LLMTimeoutError`.
- Scope creep: the hybrid filter, JSON-output/schema, and source expansion (HF Daily Papers, HN Algolia, P2 feeds) are OTHER MVP-2 slices — keep this adapter to prompt-in / typed-response-out only.
- Persistence: hybrid backend requested (Engram + openspec file). This executor has no Write tool, so the `openspec/changes/mvp-2-ollama-adapter/exploration.md` mirror was written by the propose phase; Engram half saved during exploration.

## Ready for Proposal
Yes. Scope is tight and well-bounded (roadmap MVP-2 slice 1 + architecture `synthesis/llm.py`). Proceed to `sdd-propose` to resolve the 8 decisions above (chiefly generate-vs-chat, error shape, and default model/timeout).
