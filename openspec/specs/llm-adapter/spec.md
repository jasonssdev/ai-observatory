# llm-adapter Specification

## Purpose

Provide a thin, resilient local Ollama LLM adapter behind a typed `LLMClient`
port. It sends a prompt to a configured Ollama model over `POST /api/generate`
(non-streaming) and returns a typed `LLMResponse`, or raises a typed
`LLMError` on failure. It never swallows failures.

## Non-Goals

- Hybrid filter / classification logic (later slice).
- Structured/JSON output (`format`), system prompts, `/api/chat`.
- Source expansion (HF Daily Papers, HN Algolia, P2 feeds).
- Retry/backoff, streaming, async execution.

## Requirements

### Requirement: Successful Generation
The system MUST send `prompt` to the configured Ollama model via
`POST /api/generate` with `stream: false`, and on an HTTP `200` response
containing valid JSON with a `response` field, MUST return an `LLMResponse`
whose `text` equals the `response` field, `model` equals the configured
model, and `raw` equals the full parsed body.

#### Scenario: Valid response returns typed result
- GIVEN a reachable Ollama server configured with model `llama3.2`
- WHEN `generate("hello")` is called and the server returns HTTP 200 with
  `{"response": "hi there", ...}`
- THEN an `LLMResponse` is returned with `text == "hi there"`,
  `model == "llama3.2"`, and `raw` equal to the full parsed body

### Requirement: Server Unreachable Handling
The system MUST raise `LLMUnavailableError` when the Ollama server cannot be
reached (connection refused or no server listening).

#### Scenario: Connection refused
- GIVEN no Ollama server is listening at the configured URL
- WHEN `generate(prompt)` is called
- THEN `LLMUnavailableError` is raised and no `LLMResponse` is returned

### Requirement: Timeout Handling
The system MUST raise `LLMTimeoutError` when the request exceeds the
configured timeout.

#### Scenario: Request exceeds timeout
- GIVEN a configured timeout of `T` seconds and a server that does not
  respond within `T`
- WHEN `generate(prompt)` is called
- THEN `LLMTimeoutError` is raised

### Requirement: Model Not Found Handling
The system MUST raise `LLMModelNotFoundError` when Ollama responds with HTTP
`404` and an error body indicating the model is not found.

#### Scenario: Unpulled model
- GIVEN the configured model is not pulled on the Ollama server
- WHEN `generate(prompt)` is called and the server returns HTTP 404 with
  `{"error": "model 'x' not found ..."}`
- THEN `LLMModelNotFoundError` is raised

### Requirement: Malformed Response Handling
The system MUST raise `LLMResponseError` when the response body is not valid
JSON, or is valid JSON missing the `response` field.

#### Scenario: Non-JSON body
- GIVEN the server returns HTTP 200 with a non-JSON body
- WHEN `generate(prompt)` is called
- THEN `LLMResponseError` is raised

#### Scenario: Missing response field
- GIVEN the server returns HTTP 200 with valid JSON lacking a `response` key
- WHEN `generate(prompt)` is called
- THEN `LLMResponseError` is raised

### Requirement: Configuration-Driven Settings
The system MUST resolve the Ollama endpoint URL, model name, and request
timeout from `AIOBS_OLLAMA_URL`, `AIOBS_OLLAMA_MODEL`, and
`AIOBS_OLLAMA_TIMEOUT_SECONDS`, defaulting respectively to
`http://localhost:11434`, `qwen2.5:7b`, and `60.0` seconds when unset,
missing, or invalid.

#### Scenario: Defaults apply when unset
- GIVEN no `AIOBS_OLLAMA_*` environment variables are set
- WHEN configuration is resolved
- THEN `ollama_url == "http://localhost:11434"`,
  `ollama_model == "qwen2.5:7b"`, and `ollama_timeout_seconds == 60.0`

#### Scenario: Overrides apply when set
- GIVEN `AIOBS_OLLAMA_URL`, `AIOBS_OLLAMA_MODEL`, and
  `AIOBS_OLLAMA_TIMEOUT_SECONDS` are set to valid values
- WHEN configuration is resolved
- THEN each field equals its corresponding environment value

### Requirement: Injectable HTTP Client
The system MUST accept an optional pre-constructed `httpx.Client` at adapter
construction; when none is provided, it MUST create and use one scoped to
each call.

#### Scenario: Injected client is used directly
- GIVEN an `httpx.Client` instance is injected at construction (e.g. bound to
  a `MockTransport`)
- WHEN `generate(prompt)` is called
- THEN the injected client issues the request and no new client is
  constructed

#### Scenario: No client injected
- GIVEN no `httpx.Client` is injected at construction
- WHEN `generate(prompt)` is called
- THEN a new `httpx.Client` scoped to that call is created, used, and closed
