# Tasks: MVP-2 Ollama Local-LLM Adapter

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~320-390 (config.py +~25, synthesis/__init__.py +~3, synthesis/llm.py +~140, test_llm.py +~180, test_config.py +~40) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|------------------|--------------------|
| 1 | Config extension + `synthesis/llm.py` (`LLMResponse`, `LLMError` hierarchy, `LLMClient` Protocol, `OllamaClient`) | PR 1 | `uv run pytest tests/unit/test_config.py tests/unit/test_llm.py -q` | N/A — pure `httpx.MockTransport`, zero network; no live Ollama in this slice | Revert `config.py` diff + delete `synthesis/`; nothing else depends on `synthesis/` yet |

## Phase 1: Config Foundation (`config.py`)

- [x] 1.1 RED `test_config.py::test_float_env` — table: unset->default, valid override, invalid string->default, negative->default
- [x] 1.2 GREEN `_float_env(name, default)` in `config.py`, mirrors `_int_env`
- [x] 1.3 RED `test_config.py::test_ollama_settings` — no env -> `ollama_url=="http://localhost:11434"`, `ollama_model=="llama3.2"`, `ollama_timeout_seconds==60.0`; `AIOBS_OLLAMA_*` set -> each field overridden
- [x] 1.4 GREEN add `ollama_url`/`ollama_model`/`ollama_timeout_seconds` fields to `Config` + `from_env` wiring via `AIOBS_OLLAMA_URL`/`AIOBS_OLLAMA_MODEL`/`_float_env("AIOBS_OLLAMA_TIMEOUT_SECONDS", 60.0)`

## Phase 2: Typed Contract Scaffold (`synthesis/`)

- [x] 2.1 Create `src/ai_observatory/synthesis/__init__.py` (package marker)
- [x] 2.2 Create `synthesis/llm.py`: frozen `LLMResponse(text: str, model: str, raw: dict)`, `LLMError` base + `LLMUnavailableError`/`LLMTimeoutError`/`LLMModelNotFoundError`/`LLMResponseError` subclasses, `LLMClient(Protocol)` with `generate(prompt: str) -> LLMResponse`

## Phase 3: `OllamaClient` Adapter (`synthesis/llm.py`, TDD via `tests/unit/test_llm.py`)

- [x] 3.1 RED `test_generate_success` — `MockTransport` returns 200 `{"response": "hi there", "model": "llama3.2"}`; assert `LLMResponse.text/model/raw`; handler asserts request body `{model, prompt, stream: false}`
- [x] 3.2 GREEN `OllamaClient.__init__(url, model, timeout, client=None)` + `generate()` happy path: `POST {url}/api/generate`, parse JSON, return `LLMResponse`
- [x] 3.3 RED `test_generate_unreachable` — handler raises `httpx.ConnectError` -> `LLMUnavailableError`
- [x] 3.4 GREEN catch `httpx.ConnectError` -> raise `LLMUnavailableError`
- [x] 3.5 RED `test_generate_timeout` — handler raises `httpx.ReadTimeout` -> `LLMTimeoutError`
- [x] 3.6 GREEN catch `httpx.TimeoutException` (before `ConnectError`, per design ordering) -> raise `LLMTimeoutError`
- [x] 3.7 RED `test_generate_model_not_found` — canned 404 `{"error": "model 'x' not found"}` -> `LLMModelNotFoundError`
- [x] 3.8 GREEN catch `httpx.HTTPStatusError`, inspect `response.status_code == 404` -> `LLMModelNotFoundError`; other non-2xx -> `LLMResponseError`
- [x] 3.9 RED `test_generate_non_json_body` and `test_generate_missing_response_key` — non-JSON 200 body, and valid-JSON-200-missing-`response` -> both raise `LLMResponseError`
- [x] 3.10 GREEN catch `json.JSONDecodeError`/`KeyError` -> raise `LLMResponseError`
- [x] 3.11 RED `test_generate_uses_injected_client_directly` — injected `httpx.Client` issues the request, no new client constructed
- [x] 3.12 GREEN when `client` is provided at construction, use it directly (no `with httpx.Client(...)`)
- [x] 3.13 RED `test_generate_creates_scoped_client_when_none_injected` — no client injected -> per-call `httpx.Client` created with explicit `httpx.Timeout(connect/read/write/pool=timeout_seconds)`, used, and closed
- [x] 3.14 GREEN implement per-call `with httpx.Client(timeout=...) as client:` block mirroring `HttpxFetcher`

## Phase 4: Failure-Mode Ordering & Final Gates

- [x] 4.1 Verify `except` clause order in `generate()`: `httpx.TimeoutException` before `httpx.ConnectError` before `httpx.HTTPStatusError` before JSON/key errors, matching the design's failure-mode table; add/keep a regression assertion (e.g. `httpx.ReadTimeout` subclass) that it resolves to `LLMTimeoutError`, not `LLMUnavailableError`
- [x] 4.2 Run full suite `uv run pytest` — all green
- [x] 4.3 Run `uv run ruff check .` — clean
