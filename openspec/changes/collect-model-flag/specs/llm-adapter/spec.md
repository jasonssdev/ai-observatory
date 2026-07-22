# Delta for llm-adapter

## MODIFIED Requirements

### Requirement: Configuration-Driven Settings
The system MUST resolve the Ollama endpoint URL, model name, and request
timeout from `AIOBS_OLLAMA_URL`, `AIOBS_OLLAMA_MODEL`, and
`AIOBS_OLLAMA_TIMEOUT_SECONDS`, defaulting respectively to
`http://localhost:11434`, `qwen2.5:7b`, and `60.0` seconds when unset,
missing, or invalid.
(Previously: the default model was `llama3.2`.)

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
