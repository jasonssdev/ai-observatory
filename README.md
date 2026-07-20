# AI Observatory

A personal, local-first system that watches the AI ecosystem every day, keeps a record you can revisit at any time, and once a week distills it into a short, ranked list of the topics that actually matter — the research material for your content.

Keeping up with AI by hand does not scale. The important developments — new models, papers, releases, funding, regulation, open source — are spread across dozens of sources. AI Observatory does the watching for you, so your attention goes to understanding and creating, not searching.

## How it works

The system runs on two rhythms:

- **Every day — observe and accumulate.** It checks a curated list of trusted sources, keeps the significant AI developments, and stores them as a structured local record. Each daily record is useful on its own; the record grows day by day and nothing is lost between runs.
- **Once a week — synthesize.** It reviews everything accumulated that week and produces a short, ranked list answering one question: *what changed this week, and why does it matter?* That weekly briefing is the material you use to create videos, articles, newsletters, or posts.

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

## Status

Planning stage. The design is documented; implementation has not started yet. See [docs/roadmap.md](docs/roadmap.md) for the MVP plan and [AGENTS.md](AGENTS.md) for the intended project layout.

## Setup

_To be added with the first code contribution._ The first version will ship a `pyproject.toml` with the setup, run, lint, and test commands documented here.

```bash
# Placeholder — not implemented yet
# uv sync
# ai-observatory collect     # run the daily collection
# ai-observatory synthesize  # build the weekly briefing
```
