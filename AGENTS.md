# Repository Guidelines

## Project Structure & Module Organization

This repository is in its planning stage. `README.md` provides the project entry point, while `docs/vision.md` defines the product goals, scope, and guiding principles. Keep additional design notes in `docs/` and use descriptive, lowercase filenames such as `docs/source-selection.md`.

There is not yet an application or test directory. When implementation begins, prefer a conventional Python layout: production code under `src/ai_observatory/` and tests under `tests/`, with test paths mirroring the source modules. Keep generated daily records, weekly briefings, caches, credentials, and virtual environments out of source directories.

## Build, Test, and Development Commands

No build system, dependency manifest, or test runner is configured yet. Documentation-only changes can be reviewed with:

```bash
git diff --check
git diff -- README.md docs/
```

The first code contribution should add a reproducible project manifest (for example, `pyproject.toml`) and document its setup, run, lint, and test commands in `README.md` and here. Do not rely on undeclared global packages.

## Coding Style & Naming Conventions

Write Markdown with short sections, sentence-case headings, and one idea per paragraph. Preserve the local-first, traceable, human-reviewed principles in `docs/vision.md`.

For future Python code, use 4-space indentation, `snake_case` for modules and functions, `PascalCase` for classes, and type hints on public interfaces. Prefer small modules organized by responsibility (collection, storage, and synthesis). Add formatter and linter configuration to `pyproject.toml` before enforcing a tool in CI.

## Testing Guidelines

No testing framework or coverage threshold exists yet. New executable behavior should include automated tests in `tests/`; name files `test_<module>.py` and tests `test_<behavior>()`. Cover success paths, malformed source data, duplicate records, and failures that could break source traceability. Document the selected runner and exact command when introducing it.

## Commit & Pull Request Guidelines

History currently contains only `Initial commit`, so no formal convention is established. Use concise, imperative subjects such as `Add daily record schema`, and keep unrelated changes separate.

Pull requests should explain the problem and approach, list validation performed, and link relevant issues. Include sample output for record or briefing changes and screenshots only for visual changes. Call out configuration, storage-format, or source-list migrations explicitly.

## Security & Configuration

Never commit `.env` files, API keys, tokens, local records containing sensitive data, or machine-specific paths. Provide sanitized examples for new configuration and keep cloud integrations optional and intentional.
