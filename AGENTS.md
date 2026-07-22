# Repository Guidelines

## Project Structure & Module Organization

This repository implements MVP 1 (daily record) and MVP 2 (signal filter); MVP 3 (weekly briefing + scheduling) and v1.0 (bridged/Apify sources, hardening) have not started. `README.md` provides the project entry point, while `docs/vision.md` defines the product goals, scope, and guiding principles. Keep additional design notes in `docs/` and use descriptive, lowercase filenames such as `docs/source-selection.md`.

Production code lives under `src/ai_observatory/`, organized by responsibility: `collection/` (collectors, dedup, source loading), `storage/` (SQLite access, record rendering, models), `synthesis/` (the hybrid filter and LLM client), plus `cli.py` and `config.py`. Tests live under `tests/`, split into `unit/`, `integration/`, `smoke/`, and shared `fixtures/`. Keep generated daily records, weekly briefings, caches, credentials, and virtual environments out of source directories.

## Build, Test, and Development Commands

The project uses [`uv`](https://docs.astral.sh/uv/) with a `pyproject.toml`; pytest and ruff are already configured there. Common commands:

```bash
uv sync                       # install dependencies (including dev group)
uv run ai-observatory collect # run the daily collection pipeline
uv run pytest                 # run the test suite
uv run ruff check .           # lint
```

Do not rely on undeclared global packages; add dependencies through `pyproject.toml` and `uv`.

## Coding Style & Naming Conventions

Write Markdown with short sections, sentence-case headings, and one idea per paragraph. Preserve the local-first, traceable, human-reviewed principles in `docs/vision.md`.

For Python code, use 4-space indentation, `snake_case` for modules and functions, `PascalCase` for classes, and type hints on public interfaces. Prefer small modules organized by responsibility (collection, storage, and synthesis). Ruff is the configured linter and formatter (`uv run ruff check .`).

## Testing Guidelines

Tests run under pytest (`uv run pytest`) and live in `tests/` (`unit/`, `integration/`, `smoke/`, `fixtures/`). New executable behavior should include automated tests; name files `test_<module>.py` and tests `test_<behavior>()`. Cover success paths, malformed source data, duplicate records, and failures that could break source traceability.

## Commit & Pull Request Guidelines

History follows [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `chore:`, `docs:` prefixes with a concise, imperative subject (e.g. `feat(cli): show live progress bars during collect`). Keep unrelated changes in separate commits.

Pull requests should explain the problem and approach, list validation performed, and link relevant issues. Include sample output for record or briefing changes and screenshots only for visual changes. Call out configuration, storage-format, or source-list migrations explicitly.

## Security & Configuration

Never commit `.env` files, API keys, tokens, local records containing sensitive data, or machine-specific paths. Provide sanitized examples for new configuration and keep cloud integrations optional and intentional.
