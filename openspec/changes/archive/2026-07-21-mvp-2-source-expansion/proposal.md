# Proposal: MVP-2 Source Expansion (JSON APIs + P2 feeds)

## Intent

Coverage today is 9 RSS/Atom feeds; the highest signal-to-noise tiers in
`docs/source-selection.md` (HF Daily Papers, Hacker News) are JSON APIs the
pipeline cannot ingest, and the strongest P2 feeds are unused. This slice
broadens coverage two ways: (1) two dedicated JSON-API collectors that threshold
the research/community firehose by `upvotes`/`points` before storage, and (2)
config-only P2 RSS additions. It closes the `architecture.md` drift that falsely
claims JSON APIs run through `RssCollector` (impossible — `parse_feed` is
feedparser/RSS-Atom only). Firehose thresholding satisfies the roadmap's
"score cutoff" at collection time, with no hybrid-filter change.

## Scope

### In Scope
- NEW `collection/hf_papers.py`: pure `parse_hf_papers(bytes, min_upvotes, max_chars)` + `HfPapersCollector` (canonical `https://huggingface.co/papers/{paper.id}`, threshold `paper.upvotes`).
- NEW `collection/hn_algolia.py`: pure `parse_hn_algolia(bytes, min_points, max_chars)` + `HnAlgoliaCollector` (canonical = external `hits[].url`, permalink fallback when null, threshold `points`).
- Both reuse `HttpxFetcher`, satisfy the `Collector` Protocol, and log+return `[]` on failure/malformed JSON (never raise) — mirroring `RssCollector`/`parse_feed`.
- MODIFY `collection/sources.py`: `load_sources` returns ALL valid sources (stop hard-filtering to `rss`).
- MODIFY `cli.py`: build a `{collector: Collector}` dispatch map (`rss`→Rss, `hf_papers`→HfPapers, `hn_algolia`→HnAlgolia); per source pick collector, unknown→log+skip.
- MODIFY `config.py`: `AIOBS_HF_MIN_UPVOTES` (default 5), `AIOBS_HN_MIN_POINTS` (default 30) via `_int_env`.
- MODIFY `sources.yaml`: add HF + HN JSON sources + a focused P2 RSS subset (Key Decision 8).
- MODIFY `docs/architecture.md`: correct the collector table/example so JSON APIs use their dedicated collectors, not `collector: rss`.
- Tests (strict TDD): per-collector fixtures + CLI dispatch + JSON-vs-RSS dedup (Testing Plan).

### Out of Scope (non-goals)
- Bridged/RSSHub sources, Apify/X sources — v1.0.
- Weekly briefing, `synthesize` CLI, scheduling — MVP-3.
- Changing the hybrid filter; adding an `Item.score` column / storage migration.
- Server-side vs client-side threshold optimization beyond the basic cutoff.
- A generic config-driven `JsonCollector` (rejected — see Key Decision 1).

## Capabilities

### New Capabilities
- `json-collection`: fetch bespoke JSON APIs (HF Daily Papers, HN Algolia) and normalize to `Item`s with an in-collector threshold drop (score retained in `raw`), per-source canonical-URL construction + null-url fallback, and log+return-`[]` failure isolation.

### Modified Capabilities
- `collect-cli`: dispatch each source to its collector by `source.collector` (replacing the single `RssCollector` loop); `load_sources` returns all valid sources; new `AIOBS_HF_MIN_UPVOTES` / `AIOBS_HN_MIN_POINTS` config wiring (fail-safe to defaults).

> **NOT modified**: `feed-collection` (RSS/Atom requirements unchanged; P2 feeds are
> pure config reusing `RssCollector`). `item-storage` (no schema change). `item-deduplication`
> (existing canonical-URL + title-hash dedup already handles JSON items).

## Approach

Exploration **Approach A + Score-Approach 1**. Two dedicated collectors, each a
pure `parse_*` function mirroring `parse_feed` plus a thin collector that
fetch→parse→stamps source/priority/category. Thresholding lives INSIDE the
collector (drop below-cutoff items before returning) so cutoffs are testable
without live APIs; scores survive in `raw` for a future filter enhancement, so
the slice is migration-free. `Source.collector` is already the discriminator, so
`base.py` is untouched; the CLI gains a small dispatch map. P2 feeds are pure
`sources.yaml` additions reusing `RssCollector`. JSON items flow through the
existing dedup unchanged.

### Key Decisions (resolves the exploration's open questions)
| # | Decision |
|---|----------|
| 1 | **Two dedicated collectors**, not a generic `JsonCollector`. HF nesting (`paper.upvotes`), URL construction, and HN permalink/null-url fallback do not reduce to a clean generic field-map; explicit collectors match `parse_feed` and are trivially table-testable. |
| 2 | **Threshold inside the collector** (not in the filter). Firehose cutoff is a property of the source; keeps the hybrid filter out of scope and makes the drop unit-testable via injected fetcher. |
| 3 | **No `Item.score` column.** `upvotes`/`points` are retained in `raw`; a future hybrid-filter enhancement can read them. Avoids a storage migration this slice. |
| 4 | **Discriminator names**: `hf_papers`, `hn_algolia` (explicit over generic `api`). |
| 5 | **Default thresholds**: `AIOBS_HF_MIN_UPVOTES=5`, `AIOBS_HN_MIN_POINTS=30` (matches source-selection). Both env-tunable via `_int_env` (fail-safe, reject negative). |
| 6 | **HN canonical URL** = external `hits[].url` when present (so HN dedups against primary feeds), else the HN permalink `.../item?id={objectID}`; permalink always kept in `raw`. **HF canonical** = `https://huggingface.co/papers/{id}` (title-hash dedups vs arXiv; P1 HF wins the tie). |
| 7 | **HN source URL** also carries `numericFilters=points>N` for payload reduction, but the collector-side drop remains authoritative (defense in depth). |
| 8 | **Focused P2 subset** (priority 2, from source-selection.md): Google Research (research), Qwen (lab), arXiv cs.AI + cs.CL (research), Reddit r/LocalLLaMA (community), Ahead of AI + Latent Space + The Decoder + Ben's Bites (newsletter), VentureBeat AI + TechCrunch AI + MIT Tech Review AI (news), Ollama + HF Blog (tooling). Excludes P3/broad/noisy feeds. |
| 9 | **Fix `architecture.md`** collector table/example to reflect dedicated JSON collectors (doc-drift correction). |

## Testing Plan (strict TDD — injected/fake fetcher, NEVER live APIs)
- `tests/unit/test_hf_papers.py`: valid JSON→normalized Items; below-upvotes dropped; nested `paper.upvotes` extraction; malformed/unexpected JSON→`[]` (no raise); empty array→`[]`.
- `tests/unit/test_hn_algolia.py`: valid→Items; below-points dropped; null external `url`→permalink fallback (permalink in `raw`); malformed→`[]`; empty hits→`[]`.
- `tests/unit/test_sources.py`: update — non-`rss` sources are now returned, not filtered.
- CLI dispatch test: each `collector` value routes to the matching collector; unknown→log+skip.
- Dedup test: a JSON item and an RSS item for the same story collapse (canonical URL for HN external link; title-hash for HF-vs-arXiv, P1 wins).
- `uv run pytest` green, `uv run ruff check .` clean.

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `collection/hf_papers.py` | New | `parse_hf_papers` + `HfPapersCollector`. |
| `collection/hn_algolia.py` | New | `parse_hn_algolia` + `HnAlgoliaCollector`. |
| `collection/sources.py` | Modified | Return all valid sources (drop `rss`-only filter). |
| `cli.py` | Modified | Collector dispatch map; reuse `HttpxFetcher`. |
| `config.py` | Modified | `AIOBS_HF_MIN_UPVOTES`, `AIOBS_HN_MIN_POINTS`. |
| `sources.yaml` | Modified | HF + HN + P2 RSS subset. |
| `docs/architecture.md` | Modified | Fix JSON-via-RssCollector drift. |
| `tests/**` | New/Modified | Per-collector, dispatch, dedup, sources. |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Live JSON shape drift (`paper.upvotes`, null `url`) | Med | Pin with fixtures; `parse_*` never raises (log+`[]`). |
| Threshold too aggressive (empty firehose) / too loose (noise) | Med | Env-tunable `AIOBS_*`; sensible defaults; documented. |
| HN external-url dedup suppresses a discussion-is-the-point story | Low | Accepted; permalink retained in `raw`. |
| P2 feed URL rot / new feed unreachable | Low | Per-source failure isolation already covers it (run continues). |
| Doc drift reintroduced | Low | Fix `architecture.md` in this slice; call out in review. |

## Rollback Plan
Additive slice. Revert the change branch; the two new modules disappear and the
CLI falls back to the `rss`-only path. `sources.yaml` JSON/P2 entries can be
removed independently. No schema change, no data unwind (`data/` gitignored).

## Dependencies
None new. Reuses `HttpxFetcher`, `Collector` Protocol, `dedup`, stdlib `json`.
Runtime-only: HF/HN endpoints reachable during integration/smoke — never in unit tests.

## Success Criteria
- [ ] `collect` ingests HF Daily Papers and HN Algolia, thresholded before storage.
- [ ] Below-cutoff items are dropped; retained score lives in `raw`.
- [ ] Each source routes to its collector by `collector`; unknown→log+skip.
- [ ] JSON items dedup against RSS items (canonical URL + title-hash).
- [ ] P2 feeds ingested via `RssCollector` with `priority: 2`.
- [ ] `architecture.md` no longer claims JSON APIs use `collector: rss`.
- [ ] `uv run pytest` green, `uv run ruff check .` clean.

## Size / PR Forecast (budget: 800 changed lines)
Estimate ~430-580 changed lines: `hf_papers.py` (~70-100), `hn_algolia.py`
(~70-100), `sources.py` delta (~10-20), `cli.py` delta (~30-50), `config.py`
delta (~15), `sources.yaml` + `architecture.md` (~50-70), tests (~180-240).
`400-line budget risk: Medium` (exceeds the 400 default; within the 800 session
budget). `Chained PRs recommended: No` — one cohesive slice; a natural 2-PR
split exists if review load is a concern: (1) two JSON collectors + config +
tests, (2) CLI dispatch + `sources.yaml`/`architecture.md`. `Decision needed
before apply: No` under the 800-line budget.
