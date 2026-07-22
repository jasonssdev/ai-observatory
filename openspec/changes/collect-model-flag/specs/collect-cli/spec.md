# Delta for collect-cli

## ADDED Requirements

### Requirement: Model Override Flag
`collect` MUST accept an optional `--model` option. The resolved model
follows the precedence `--model` (if non-empty) > `AIOBS_OLLAMA_MODEL` env
var > config default, computed as `resolved_model = model or
config.ollama_model` and passed to `OllamaClient`. The resolved model MUST be
recorded in `item_significance.model` for the run's classified items. An
empty `--model` value MUST NOT raise an error; it falls back like an omitted
flag. A resolved model that is not installed on the Ollama server MUST NOT
crash the run; it degrades to deterministic-only mode via the existing
`LLMModelNotFoundError` handling.

#### Scenario: Flag override reaches the client and provenance
- GIVEN `collect --model qwen2.5:7b` is invoked
- WHEN the run classifies at least one item via the LLM
- THEN `OllamaClient` is constructed with `qwen2.5:7b` and the resulting
  `item_significance.model` value is `qwen2.5:7b`

#### Scenario: Env var used when no flag is passed
- GIVEN `AIOBS_OLLAMA_MODEL` is set and `collect` is invoked without
  `--model`
- WHEN the run classifies at least one item via the LLM
- THEN `OllamaClient` is constructed with the env var's model

#### Scenario: Config default used when neither flag nor env is set
- GIVEN no `--model` flag and no `AIOBS_OLLAMA_MODEL` env var
- WHEN `collect` runs and classifies at least one item via the LLM
- THEN `OllamaClient` is constructed with the config default model
  (`qwen2.5:7b`)

#### Scenario: Flag takes precedence over env var
- GIVEN `AIOBS_OLLAMA_MODEL` is set to one model and `--model` is passed
  with a different model
- WHEN `collect` runs
- THEN `OllamaClient` is constructed with the `--model` value, not the env
  var's value

#### Scenario: Empty flag value falls back to config default
- GIVEN `collect --model ""` is invoked with no `AIOBS_OLLAMA_MODEL` set
- WHEN `collect` runs
- THEN it does not raise an error and `OllamaClient` is constructed with the
  config default model

#### Scenario: Not-installed model degrades gracefully
- GIVEN `--model` resolves to a model not pulled on the Ollama server
- WHEN `collect` runs and attempts a classification
- THEN `LLMModelNotFoundError` is raised internally, the run degrades to
  deterministic-only mode, and `collect` exits 0 without crashing
