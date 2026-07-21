# Architecture

Technical design for AI Observatory. This document turns the goals in [vision.md](vision.md) and the sources in [source-selection.md](source-selection.md) into a buildable structure. It defines the pipeline, the data model, the storage format, how sources are collected, how work is scheduled, and what belongs in the first version.

It is a design reference, not a specification of finished code — the repo is in planning stage.

## Design principles (applied)

The [vision principles](vision.md#principles) constrain the architecture directly:

- **Local-first** → SQLite and Markdown files on disk are the source of truth. Any network call is a read of an external source, never a dependency for reading your own data. Cloud collectors (Apify) are optional and off by default.
- **Traceable** → every stored item and every line of the weekly briefing carries a link back to its origin. Nothing enters a summary without a source URL behind it.
- **Signal over noise** → filtering happens early (at collection and daily synthesis), so the weekly step reasons over a clean set, not the raw firehose.
- **Daily record, weekly synthesis** → two separate entry points on two schedules, sharing one store.

## Pipeline overview

Three stages, one direction of data flow. Each stage is a module with a single responsibility, as anticipated in [AGENTS.md](../AGENTS.md).

```
                 ┌──────────────┐
   sources ────▶ │  COLLECTION  │  fetch, normalize, deduplicate
  (feeds/APIs)   └──────┬───────┘
                        │  Item records
                        ▼
                 ┌──────────────┐
                 │   STORAGE    │  SQLite (query/dedup) + Markdown (read)
                 └──────┬───────┘
                        │
              ┌─────────┴──────────┐
              ▼                    ▼
      ┌──────────────┐     ┌──────────────┐
      │ DAILY        │     │ WEEKLY       │
      │ SYNTHESIS    │     │ SYNTHESIS    │
      │ filter/rank  │     │ rank + brief │
      └──────┬───────┘     └──────┬───────┘
             ▼                    ▼
      records/<date>.md     briefings/<week>.md
```

Collection and daily synthesis run once a day; weekly synthesis runs once a week over the accumulated store.

## Module layout

Conventional Python layout per [AGENTS.md](../AGENTS.md): production code under `src/ai_observatory/`, tests mirroring it under `tests/`.

```
src/ai_observatory/
  collection/
    base.py          # Collector interface (abstract)
    rss.py           # RssCollector — the default engine
    apify.py         # ApifyCollector — optional, for X/Twitter (off by default)
    rsshub.py        # RsshubCollector — optional, for no-RSS blogs
    sources.py       # loads sources.yaml, applies priorities
    dedup.py         # canonical-URL + title-hash deduplication
  storage/
    db.py            # SQLite access
    records.py       # daily Markdown record writer
    models.py        # Item, DailyRecord, WeeklyBriefing dataclasses/schema
  synthesis/
    daily.py         # filter + classify the day's items
    weekly.py        # rank topics, build the briefing
    llm.py           # LLM client abstraction (local or API)
  config.py          # settings, paths, secrets from .env
  cli.py             # `collect`, `synthesize` entry points
data/                # gitignored — the local store
  observatory.db
  records/<YYYY-MM-DD>.md
  briefings/<YYYY-Www>.md
sources.yaml         # the source list as config (see below)
```

`data/`, `.env`, and virtual environments stay out of source control (see [AGENTS.md](../AGENTS.md#security--configuration)).

## Data model

Three shapes. Keep them small and stable — storage format changes are a migration.

**Item** — one normalized development, the atomic unit. Produced by every collector regardless of source type.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | str | Stable hash of canonical `url` (dedup key). |
| `title` | str | |
| `url` | str | Canonical (UTM/tracking params stripped). |
| `source` | str | Source name from `sources.yaml`. |
| `source_priority` | int | 1 / 2 / 3, from the source list. Drives filtering and ranking. |
| `category` | str | e.g. `lab`, `research`, `newsletter`, `news`, `tooling`, `community`. |
| `published_at` | datetime | UTC. |
| `collected_at` | datetime | UTC. |
| `summary` | str | Short text from the feed (not the full article). |
| `raw` | json | Original entry, kept for traceability and reprocessing. |

**DailyRecord** — the set of the day's kept Items plus the daily synthesis output, serialized to `records/<date>.md`. Readable on its own; this is what you open to see "what happened that day."

**WeeklyBriefing** — the ranked list of topics for the week, serialized to `briefings/<week>.md`. Each topic has a title, a one-line "why it matters," and the source links behind it.

Traceability rule: a topic in a briefing must reference at least one Item, and every Item has a real `url`. The synthesis layer may not invent a topic without a backing Item.

## Collection layer

All collectors implement one interface, so the rest of the system never knows or cares how an item was fetched. This is what lets the optional cloud collectors be switched off without affecting anything.

```python
class Collector(Protocol):
    def collect(self, source: Source) -> list[Item]: ...
```

| Collector | Handles | Default | Notes |
| --- | --- | --- | --- |
| `RssCollector` | RSS/Atom feeds | **on** | The engine. Covers most sources in [source-selection.md](source-selection.md) with no cost or auth. |
| `HfPapersCollector` | Hugging Face Daily Papers JSON API | **on** | Dedicated collector: nested `paper.upvotes` scoring, canonical `https://huggingface.co/papers/{id}` URLs. Thresholded by `AIOBS_HF_MIN_UPVOTES`. |
| `HnAlgoliaCollector` | Hacker News Algolia JSON API | **on** | Dedicated collector: external `url` when present, discussion permalink fallback otherwise. Thresholded by `AIOBS_HN_MIN_POINTS`. |
| `RsshubCollector` | Official blogs with no RSS (Anthropic, Meta, Mistral, xAI, DeepSeek, The Batch) via a self-hosted RSSHub instance | optional | Local Docker; fits local-first. Anthropic is the top bridge priority. |
| `ApifyCollector` | X/Twitter accounts (zero-latency layer) via the Apify API | **off** | Paid cloud, pay-per-result. Scoped to a small curated account list. Kept behind the same interface so the system runs fine without it. |

Sources live in `sources.yaml`, not in code, so adding coverage is a config edit — matching the vision that coverage is defined by the source list:

```yaml
- name: OpenAI
  collector: rss
  url: https://openai.com/news/rss.xml
  category: lab
  priority: 1
- name: Hugging Face Daily Papers
  collector: hf_papers      # dedicated JSON-API collector
  url: https://huggingface.co/api/daily_papers
  category: research
  priority: 1
- name: Anthropic
  collector: rsshub        # bridged, no official feed
  route: /anthropic/news
  category: lab
  priority: 1
```

Collection responsibilities: fetch with a real `User-Agent`, parse, normalize to `Item`, then deduplicate. Deduplication is by canonical URL plus a title hash — the same story arrives through multiple feeds, and the daily record must not repeat it. Failures (a dead feed, malformed XML, a rate-limit) are logged and skipped, never fatal: one broken source cannot stop the run.

## Storage layer

Two representations of the same data, each for a different reader:

- **SQLite (`data/observatory.db`)** — the queryable store. Deduplication, "what did we already see," and the input to synthesis. One `items` table keyed by `id`, indexed on `published_at` and `source_priority`.
- **Markdown (`data/records/<date>.md`)** — the human-readable daily record. Generated from the day's items so you can open any day and read it, exactly as the vision requires. The DB is the source of truth; Markdown is a rendered view.

Weekly briefings are written the same way to `data/briefings/<week>.md`.

## Synthesis layer

Two steps, both backed by a **local** LLM (Ollama) through a thin `llm.py` abstraction. The model never leaves your machine — hosted model APIs are explicitly out of scope for reasoning. External APIs are used *only to fetch sources* (HF Daily Papers, HN Algolia, Apify); no source data is sent to a third-party model. `llm.py` still abstracts the client so the specific local model is swappable, but the target is always local.

- **Daily** (`daily.py`) — over the day's deduplicated items, drop routine noise and classify what remains. This is a **hybrid** filter: cheap deterministic rules first (source priority + keyword/score thresholds) discard the obvious noise, then the local LLM classifies what survives. Priority-weighted — P1 sources clear the bar easily; P3 sources must earn it. Output is appended to the daily record, keeping the weekly step working over signal, not raw volume.
- **Weekly** (`weekly.py`) — over the week's kept items, answer *what changed and why it matters*. Produces a ranked list of **at most 10 topics**, each with its "why" and its source links. This is the deliverable that feeds content creation.

The LLM proposes; it never publishes and never fabricates. Every topic it emits must cite backing items — the code enforces the traceability rule rather than trusting the model.

## Scheduling

macOS `launchd` (local, survives reboots, no external scheduler needed):

- Daily agent → `ai-observatory collect` then `ai-observatory synthesize --daily`.
- Weekly agent → `ai-observatory synthesize --weekly`.

Runs are idempotent: re-running a day re-collects and re-dedupes without creating duplicates, so a missed run is safe to catch up.

## Configuration & secrets

Settings and paths in `config.py`, secrets in a gitignored `.env` with a committed sanitized `.env.example`. No API keys, tokens, or machine-specific paths in source control ([AGENTS.md](../AGENTS.md#security--configuration)). Only *source-collector* credentials (e.g. an Apify token) live in `.env` — there is no LLM API key, because the model is local. With no optional credentials set, the system runs entirely on free RSS/APIs plus the local Ollama model.

## MVP scope

The build is phased into three validatable MVPs plus a v1.0 — see [roadmap.md](roadmap.md) for the full breakdown. The list below is the **combined core** those MVPs build toward: the loop that proves the system end to end.

**Core (MVP 1–3 combined):**

- `RssCollector` + `sources.yaml` covering the P1 automatable sources.
- SQLite store + daily Markdown record with deduplication.
- Daily synthesis (filter/classify) writing the daily record.
- Weekly synthesis producing a ranked, source-linked briefing.
- `pyproject.toml`, `collect`/`synthesize` CLI, `launchd` agents, tests for the collector, dedup, and storage paths (success, malformed feed, duplicate item).

**Deferred (v1.0 and beyond):**

- `RsshubCollector` (add once the RSS loop is proven; Anthropic first).
- `ApifyCollector` for X (optional, evaluate after the core works).
- Full-text article fetching (the core uses feed summaries only).
- Any web UI — records and briefings are Markdown files.

**Explicit non-goals** (from [vision.md](vision.md#non-goals)): real-time alerting, auto-publishing, multi-user/SaaS, exhaustive crawling.

## Decisions

Resolved 2026-07-20 — these are settled, not open:

1. **LLM** — **local only, via Ollama**, for both daily filtering and the weekly briefing. Hosted model APIs are out of scope for reasoning. External APIs are permitted *only* to connect to sources (feeds, HF, HN Algolia, Apify), never to run the model.
2. **Daily filter** — **hybrid**: deterministic rules (priority + keyword/score) first, then local-LLM classification on what survives.
3. **Dependency manager** — **`uv`**, for reproducibility.
4. **Weekly briefing** — ranked, capped at **10 topics** per week.
