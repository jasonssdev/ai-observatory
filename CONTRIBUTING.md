# Contributing to AI Observatory

Thanks for your interest in contributing! AI Observatory is a personal, local-first system for watching the AI ecosystem, and contributions of all kinds are welcome: bug reports, source suggestions, documentation improvements, and code.

## Before you start

- Read [docs/vision.md](docs/vision.md) to understand what the project is — and deliberately is not. Contributions that conflict with the local-first, signal-over-noise, human-decides principles are unlikely to be accepted.
- Check [docs/roadmap.md](docs/roadmap.md) for what is planned. MVP 1 and MVP 2 are shipped; MVP 3 (weekly briefing) and v1.0 are not started.
- For anything non-trivial, open an issue first to discuss the approach before writing code.

## Development setup

Requires **Python 3.13+** and [**uv**](https://docs.astral.sh/uv/). [Ollama](https://ollama.com) is optional — without it the filter degrades gracefully to deterministic-only rules.

```bash
git clone https://github.com/jasonssdev/ai-observatory.git
cd ai-observatory
uv sync                       # install dependencies (including dev group)
uv run ai-observatory collect # run the daily collection pipeline
```

## Running tests and lint

```bash
uv run pytest            # run the test suite
uv run ruff check .      # lint
```

Both must pass before a pull request can be merged. CI runs these same commands automatically on every pull request.

## Project layout

- `src/ai_observatory/collection/` — collectors, dedup, source loading
- `src/ai_observatory/storage/` — SQLite access, record rendering, models
- `src/ai_observatory/synthesis/` — the hybrid filter and LLM client
- `src/ai_observatory/cli.py`, `config.py` — entry point and configuration
- `tests/` — split into `unit/`, `integration/`, `smoke/`, and shared `fixtures/`
- `docs/` — vision, architecture, roadmap, and source research
- `openspec/` — archived spec-driven-development artifacts documenting how each change was designed and verified

See [AGENTS.md](AGENTS.md) for the full repository guidelines (structure, style, testing, security).

## Coding conventions

- Python 3.13+, 4-space indentation, `snake_case` modules/functions, `PascalCase` classes, type hints on public interfaces.
- Small modules organized by responsibility (collection, storage, synthesis).
- Ruff is the configured linter (`uv run ruff check .`).
- New executable behavior must include tests. Name files `test_<module>.py` and tests `test_<behavior>()`. Cover success paths, malformed source data, duplicates, and failures that could break source traceability.
- Add dependencies only through `pyproject.toml` and `uv` — never rely on undeclared global packages.

## Suggesting a new source

Sources live in `sources.yaml` and are documented in [docs/source-selection.md](docs/source-selection.md). When proposing a source, explain:

1. What it covers and why it is credible (see [docs/research.md](docs/research.md) for the credibility criteria).
2. The feed or API URL and its format (RSS/Atom or JSON).
3. Expected volume — the project favors trusted sources over volume.

Use the "Source suggestion" issue template.

## Commits and pull requests

- History follows [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, etc., with a concise imperative subject (e.g. `feat(cli): show live progress bars during collect`).
- Keep unrelated changes in separate commits and separate PRs.
- PRs should explain the problem and the approach, list the validation performed, and link related issues. Include sample record output for record/briefing changes.
- Call out configuration, storage-format, or source-list migrations explicitly.

## Security

Never commit `.env` files, API keys, tokens, local records containing sensitive data, or machine-specific paths. The `data/` directory (SQLite database and daily records) is gitignored and must stay that way. To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Code of conduct

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
