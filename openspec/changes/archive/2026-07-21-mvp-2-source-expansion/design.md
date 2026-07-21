# Design: MVP-2 Source Expansion (JSON APIs + P2 feeds)

## Technical Approach

Add two dedicated JSON-API collectors that mirror `rss.py`'s three-part split — a pure `parse_*` function, a thin never-raise collector, and the shared `HttpxFetcher` — and dispatch by `source.collector` in the CLI. Thresholds live in `config.py` and reach each collector by constructor injection. Dedup, storage, and the hybrid filter are untouched. P2 coverage is pure `sources.yaml` additions reusing `RssCollector`.

## Architecture Decisions

| # | Decision | Alternatives rejected | Rationale |
|---|---|---|---|
| 1 | Two modules `hf_papers.py`, `hn_algolia.py` (pure `parse_*` + thin collector) | Single `json.py`; generic `JsonCollector` with field-map config | HF nesting + URL construction and HN null-url permalink fallback do not reduce to a clean field map; per-source modules are explicit and table-testable, matching `parse_feed`. |
| 2 | Threshold inside the collector, cutoff via constructor arg from `config.py` | Threshold in source YAML; server-side only | Keeps the hybrid filter out of scope; deterministically unit-testable; server-side `numericFilters` stays advisory, collector drop is authoritative. |
| 3 | No `Item.score` column; upvotes/points kept in `raw` | Add score column now | Migration-free; a future filter can read score from `raw`. |
| 4 | CLI `{collector: Collector}` dispatch map; unknown → log + skip | Widen `load_sources` allow-set; if/elif chain | One reuse of `HttpxFetcher`; unknown collector never crashes the run. |
| 5 | HN canonical = external `url`, permalink fallback when null | Always use HN permalink | External URL dedups HN stories against primary feeds via canonical URL; permalink retained in `raw`. |

## Data Flow

    sources.yaml ─→ load_sources (ALL valid) ─→ collect()
                                                   │
                        ┌──── dispatch[source.collector] ────┐
                        ▼            ▼                        ▼
                 RssCollector  HfPapersCollector      HnAlgoliaCollector
                        │            │                        │
                        └──── HttpxFetcher.get(url) ──────────┘
                                     │  (each: try/except → log + return [])
                                     ▼
                        parse_feed / parse_hf_papers / parse_hn_algolia
                             (pure, threshold drop, never raise)
                                     │
                        aggregate → dedup_batch → upsert → classify → render

## Interfaces / Contracts

Each collector satisfies the existing `Collector` Protocol (`collect(source) -> list[Item]`) with the same never-raise wrapper as `RssCollector` (fetch in one `try`, parse in a second, each logs + returns `[]`), then stamps `source`/`source_priority`/`category` via `dataclasses.replace`.

```python
def parse_hf_papers(data: bytes, min_upvotes: int, max_chars: int) -> list[Item]
# GET {url} → JSON array of {title, publishedAt, summary, paper:{id, upvotes, authors}}
# canonical url = https://huggingface.co/papers/{paper.id}
# published_at = publishedAt (ISO→UTC, default now); summary via normalize_summary
# drop when paper.upvotes < min_upvotes; raw = full element (upvotes retained)

def parse_hn_algolia(data: bytes, min_points: int, max_chars: int) -> list[Item]
# GET {url} → {hits:[{title, url, points, objectID, created_at}]}
# canonical = hit.url if present else https://news.ycombinator.com/item?id={objectID}
# permalink always retained in raw; published_at = created_at
# drop when points < min_points

class HfPapersCollector:  # __init__(fetcher, summary_max_chars, min_upvotes)
class HnAlgoliaCollector: # __init__(fetcher, summary_max_chars, min_points)
```

`config.py`: add `hf_min_upvotes` / `hn_min_points` fields via `_int_env("AIOBS_HF_MIN_UPVOTES", 5)` and `_int_env("AIOBS_HN_MIN_POINTS", 30)`. `cli.py` builds one `HttpxFetcher` and a dispatch map wiring config values into each collector constructor.

`sources.yaml` new entries:

```yaml
- {name: Hugging Face Daily Papers, collector: hf_papers,
   url: https://huggingface.co/api/daily_papers, category: research, priority: 1}
- {name: Hacker News (AI), collector: hn_algolia,
   url: "https://hn.algolia.com/api/v1/search_by_date?query=AI&tags=story&numericFilters=points>30",
   category: community, priority: 1}
```

Plus P2 `collector: rss` (priority 2) additions from `docs/source-selection.md`: Google Research, Qwen, arXiv cs.AI, arXiv cs.CL, Reddit r/LocalLLaMA, Ahead of AI, Latent Space, The Decoder, Ben's Bites, VentureBeat AI, TechCrunch AI, MIT Tech Review AI, Ollama, HF Blog.

## Dedup interaction

No change. HN external-url canonical collapses against primary feeds (id match); HF `papers/{id}` won't URL-match arXiv but title-hash collapses, and HF (P1) wins the tie over arXiv (P2) via `_wins`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `collection/hf_papers.py` | Create | `parse_hf_papers` + `HfPapersCollector` |
| `collection/hn_algolia.py` | Create | `parse_hn_algolia` + `HnAlgoliaCollector` |
| `collection/sources.py` | Modify | Return ALL valid sources (drop `== "rss"` filter) |
| `cli.py` | Modify | Build dispatch map; unknown collector → log + skip |
| `config.py` | Modify | Add `hf_min_upvotes` / `hn_min_points` |
| `sources.yaml` | Modify | HF + HN + P2 RSS entries |
| `docs/architecture.md` | Modify | Fix JSON-via-`RssCollector` drift (L111 + example) |
| `tests/unit/test_hf_papers.py` | Create | parse valid / below-threshold / malformed→[] / empty |
| `tests/unit/test_hn_algolia.py` | Create | valid / below-points / null-url→permalink / malformed→[] |
| `tests/unit/test_sources.py` | Modify | Non-rss sources now returned |
| `tests/unit/test_config.py` | Modify | New threshold fields + defaults |
| `tests/integration/test_collect_integration.py` | Modify | Dispatch wiring; JSON-vs-RSS dedup |
| `tests/fixtures/*.json` | Create | Canned HF + HN payloads incl. null-url, below-threshold, malformed JSON |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `parse_*` mapping, threshold drop, never-raise | Fixture JSON bytes; assert Items / `[]`; malformed & empty → `[]` |
| Unit | collector failure isolation | Injected fetcher raising → `collect` returns `[]` |
| Unit | config, `load_sources` | Defaults/env; non-rss returned |
| Integration | dispatch + JSON↔RSS dedup | MockTransport/static fetcher; unknown collector skipped |

Strict TDD: RED fixtures first. NEVER live APIs — all bytes from `tests/fixtures/`. `uv run pytest` green, `uv run ruff check .` clean.

## Threat Matrix

N/A — no shell, subprocess, VCS/PR automation, or executable-file classification. The CLI dispatch is an internal config-string → collector map (no code loaded from data); untrusted network JSON is contained by never-raise `parse_*` + fixtures.

## Migration / Rollout

No migration. Purely additive; revert-branch removes new modules and the CLI falls back to the RSS path; `sources.yaml` entries are removable.

## Non-Goals (explicit)

Bridged/RSSHub, Apify/X, weekly briefing, scheduling, hybrid-filter change, `Item.score` column, generic `JsonCollector`.

## Open Questions

None blocking. HF default upvote cutoff (5) may need env-tuning after first live run.
