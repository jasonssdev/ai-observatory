# AI Observatory

A personal, local-first system that watches the AI ecosystem every day, keeps a record you can revisit at any time, and once a week distills it into a short, ranked list of the topics that actually matter — the research material for your content.

Keeping up with AI by hand does not scale. The important developments — new models, papers, releases, funding, regulation, open source — are spread across dozens of sources. AI Observatory does the watching for you, so your attention goes to understanding and creating, not searching.

## How it works

The system runs on two rhythms:

- **Every day — observe and accumulate.** It checks a curated list of trusted sources, keeps the significant AI developments, and stores them as a structured local record. Each daily record is useful on its own; the record grows day by day and nothing is lost between runs.
- **Once a week — synthesize.** (Planned — MVP 3, not yet available.) It reviews everything accumulated that week and produces a short, ranked list answering one question: *what changed this week, and why does it matter?* That weekly briefing is the material you use to create videos, articles, newsletters, or posts.

It is a monitoring system, not a chatbot, a search engine, or an auto-publisher. It organizes and proposes; the human always decides what becomes content.

## Principles

Local-first (records and processing stay on your machine by default; cloud is optional and intentional). Trusted sources before volume. Signal over noise. Every insight traces back to its source. The system observes daily and reasons weekly. Human judgment is final.

## Documentation

| Document | What it covers |
| --- | --- |
| [docs/vision.md](docs/vision.md) | Why the project exists, what it is and isn't, principles, scope, success criteria. |
| [docs/architecture.md](docs/architecture.md) | Technical design: pipeline, data model, storage, collectors, scheduling. |
| [docs/roadmap.md](docs/roadmap.md) | The build plan — MVP 1–3 and v1.0 as validatable slices. |
| [docs/source-selection.md](docs/source-selection.md) | The operational source list — real feed/API URLs, priorities, ingestion notes. |
| [docs/research.md](docs/research.md) | Background essay on which AI sources are credible. |
| [AGENTS.md](AGENTS.md) | Repository guidelines and contribution conventions. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to set up, test, and contribute changes. |

## Status

MVP 1 (the daily record) and MVP 2 (the signal filter) are implemented and in use. `ai-observatory collect` fetches all configured sources, deduplicates, stores to SQLite, classifies each item with a hybrid deterministic + local-LLM filter, and regenerates the Markdown daily records — splitting significant developments from routine noise.

Not built yet: the weekly `synthesize` briefing and unattended scheduling (MVP 3), and the bridged (RSSHub) / optional X (Apify) sources plus hardening (v1.0). See [docs/roadmap.md](docs/roadmap.md) for the full plan.

## Setup

Requires **Python 3.13+** and [**uv**](https://docs.astral.sh/uv/). [Ollama](https://ollama.com) is optional: without it, the filter degrades gracefully to its deterministic-only rules (the run never fails).

```bash
uv sync                       # install dependencies
uv run ai-observatory collect # run the daily collection
```

`collect` writes a Markdown record per day at `data/records/<date>.md` and stores every item in the SQLite database at `data/observatory.db` (both under the gitignored `data/` directory).

The filter classifies uncertain items with a local Ollama model (default `qwen2.5:7b`). Override the model per run with `--model`:

```bash
uv run ai-observatory collect --model llama3.2
```

Precedence is `--model` > `AIOBS_OLLAMA_MODEL` env var > the config default.

### Development

```bash
uv run pytest            # run the test suite
uv run ruff check .      # lint
```

## Contributing

Contributions are welcome — bug reports, source suggestions, documentation, and code. Start with [CONTRIBUTING.md](CONTRIBUTING.md); the project follows the [Code of Conduct](CODE_OF_CONDUCT.md), and security issues should be reported per [SECURITY.md](SECURITY.md).

## License

Licensed under the [Apache License 2.0](LICENSE).
