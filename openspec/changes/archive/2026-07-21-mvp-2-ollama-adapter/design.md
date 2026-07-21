# Design: MVP-2 Ollama Local-LLM Adapter

## Technical Approach

Approach 1 (locked): sync `httpx` → `POST {url}/api/generate` with `stream:false` → parse the single JSON object → return frozen `LLMResponse` OR raise a typed `LLMError`. The adapter mirrors the mvp-1 `HttpxFetcher` seam exactly: an optional-injected `httpx.Client`, explicit `httpx.Timeout`, per-call client created inside a `with` block when none is injected. Port (`LLMClient` Protocol), typed errors, and the `OllamaClient` adapter are co-located in `synthesis/llm.py`, matching the `collection/base.py`+`rss.py` split collapsed to one file for a single backend. Strict TDD: every failure mode is driven by `httpx.MockTransport`, zero network. This fills the `synthesis/llm.py` slot from `docs/architecture.md` (lines 60-63); local-only is a hard constraint (no API key, model never leaves the machine).

## Architecture Decisions

### Decision: Failures RAISED as a typed hierarchy, never swallowed
| Option | Tradeoff | Decision |
|--------|----------|----------|
| Swallow + return empty (like `RssCollector`) | Consistent with RSS; hides availability | Rejected |
| Typed `LLMError` hierarchy raised | Diverges from RSS; caller must handle | **Chosen** |

**Rationale**: The future hybrid filter must detect whether classification actually ran to fall back to deterministic-only rules. Silent empties erase that signal. `RssCollector` swallows for per-source isolation — a different concern.

### Decision: `/api/generate`, `stream:false`, `raw: dict`
| Option | Tradeoff | Decision |
|--------|----------|----------|
| `/api/generate` (`response` field) | Simplest single-prompt shape | **Chosen** |
| `/api/chat` (`message.content`, system role) | Forward-looking; heavier now | Deferred to filter slice |

**Rationale**: Thin prompt-in/text-out adapter. `raw` holds the parsed Ollama payload (`dict`) for traceability — this supersedes the exploration's `json.dumps` string; the caller gets structured data without re-parsing.

### Decision: Per-call client lifecycle + explicit `httpx.Timeout`
**Choice**: Injected client used directly (test seam); otherwise `with httpx.Client(timeout=...)` per call. Timeout built from `httpx.Timeout(connect/read/write/pool=timeout_seconds)`, default 60.0 (LLM generation ≫ feed fetch).
**Rationale**: Byte-for-byte the `HttpxFetcher` convention; `MockTransport` injection gives deterministic tests.

## Data Flow

```
prompt ─▶ OllamaClient.generate(prompt)
             │  body {"model", "prompt", "stream": false}
             ▼
        httpx POST {url}/api/generate  ──(injected client | per-call with-block)
             │
   ┌─────────┴─────────────────────────────────────────────┐
   │ ConnectError → LLMUnavailableError                     │
   │ TimeoutException → LLMTimeoutError                     │
   │ 404 + error body → LLMModelNotFoundError               │
   │ other non-2xx / non-JSON / missing "response" →        │
   │                    LLMResponseError                    │
   └─────────┬─────────────────────────────────────────────┘
             ▼  (2xx, valid JSON, "response" present)
   LLMResponse(text=payload["response"], model, raw=payload)
```

## Failure-Mode Mapping (central concern)

| Trigger | Detection | Raised error |
|---------|-----------|--------------|
| Server down/refused | `httpx.ConnectError` | `LLMUnavailableError` |
| Request timed out | `httpx.TimeoutException` (+ `ReadTimeout`/`ConnectTimeout` subclasses) | `LLMTimeoutError` |
| Model missing | HTTP 404 (`HTTPStatusError`) w/ Ollama error body | `LLMModelNotFoundError` |
| Non-JSON body or missing `response` key | `json.JSONDecodeError` / `KeyError` | `LLMResponseError` |
| Other non-2xx | `HTTPStatusError`, status ≠ 404 | `LLMResponseError` |

Catch order: `TimeoutException` before `ConnectError` (disjoint in httpx, but explicit); inspect `HTTPStatusError.response.status_code == 404` to split model-not-found from generic non-2xx. All failures propagate — no empty returns.

## File Changes
| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/__init__.py` | Create | New package marker. |
| `src/ai_observatory/synthesis/llm.py` | Create | `LLMResponse`, `LLMError` hierarchy, `LLMClient` Protocol, `OllamaClient` adapter. |
| `src/ai_observatory/config.py` | Modify | Add `ollama_url`/`ollama_model`/`ollama_timeout_seconds` fields, `AIOBS_OLLAMA_*` wiring, `_float_env()` helper. |
| `tests/unit/test_llm.py` | Create | 5 MockTransport cases: success, unreachable, timeout, model-not-found, malformed. |
| `tests/unit/test_config.py` | Modify | Env-var table tests for the 3 new settings + `_float_env`. |

## Interfaces / Contracts

```python
# synthesis/llm.py
@dataclass(frozen=True)
class LLMResponse:
    text: str; model: str; raw: dict      # raw = parsed Ollama payload

class LLMClient(Protocol):                 # the PORT the filter depends on
    def generate(self, prompt: str) -> LLMResponse: ...

class LLMError(Exception): ...             # base
class LLMUnavailableError(LLMError): ...
class LLMTimeoutError(LLMError): ...
class LLMModelNotFoundError(LLMError): ...
class LLMResponseError(LLMError): ...

class OllamaClient:                        # the ADAPTER
    def __init__(self, url: str, model: str,
                 timeout: httpx.Timeout | float,
                 client: httpx.Client | None = None) -> None: ...
    def generate(self, prompt: str) -> LLMResponse: ...
```

**Config additions** (`AIOBS_*` override): `AIOBS_OLLAMA_URL=http://localhost:11434`, `AIOBS_OLLAMA_MODEL=llama3.2`, `AIOBS_OLLAMA_TIMEOUT_SECONDS=60.0`. `_float_env(name, default)` mirrors `_int_env`: fail-safe on missing/invalid/negative.

## Testing Strategy
| Layer | What | Approach |
|-------|------|----------|
| Unit | `generate` success | `MockTransport` → 200 `{"response": "...", "model": ...}`, assert `LLMResponse` fields incl. `raw` dict |
| Unit | Server unreachable | handler raises `httpx.ConnectError` → `LLMUnavailableError` |
| Unit | Timeout | handler raises `httpx.ReadTimeout` → `LLMTimeoutError` |
| Unit | Model not found | canned 404 + `{"error":"model '...' not found"}` body → `LLMModelNotFoundError` |
| Unit | Malformed | non-JSON body **and** valid-JSON-missing-`response` → `LLMResponseError` |
| Unit | `_float_env` / `from_env` | `monkeypatch` table: default, override, invalid→default |

Seam: tests build `httpx.Client(transport=httpx.MockTransport(handler))` and inject it into `OllamaClient(client=...)`; the request body (`model`, `prompt`, `stream:false`) is asserted inside the handler. Zero network.

## Threat Matrix
N/A — no shell, subprocess, VCS/PR automation, executable-file classification, or routing. The single HTTP call targets a config-supplied local Ollama URL via `httpx` (no shell), and every failure is typed and raised.

## Migration / Rollout
No migration. New package; three additive config fields with defaults. Nothing depends on `synthesis/` yet — revert the branch to roll back.

## Non-Goals (explicit, out of scope this slice)
Hybrid filter/classification; `format`/JSON-schema/structured output; system prompt / `/api/chat`; source expansion; retry/backoff; streaming; async; any `cli.py` or `synthesis/daily.py` change.

## Open Questions
None blocking.
