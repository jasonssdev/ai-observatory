# Exploration: MVP-2 Source Expansion (slice 3/3)

> Filesystem mirror of Engram `sdd/mvp-2-source-expansion/explore` (id 1462).
> The explore executor had no Write tool, so this file is reconstructed by the
> propose phase for openspec parity.

Add JSON-API sources (HF Daily Papers w/ upvote threshold, HN Algolia w/ points
threshold) and P2 RSS feeds. OUT of scope: bridged/RSSHub, Apify/X, weekly
briefing, scheduling, changing the hybrid filter itself.

## Current State

- **Collector seam** (`collection/base.py`): `Source(name, collector, url, category, priority)` frozen dataclass; `Fetcher` Protocol (`get(url)->bytes`); `Collector` Protocol (`collect(source)->list[Item]`, MUST log+return [] on failure, never raise).
- **RSS** (`collection/rss.py`): `HttpxFetcher` (generic bytes fetcher, streaming, capped 10MB, real UA, follows redirects, injectable httpx client for tests) + pure `parse_feed(bytes,max_chars)->list[Item]` using **feedparser** + `RssCollector` (fetch→parse→stamp source/priority/category via `dataclasses.replace`). Per-source failure isolation is in the collector.
- **sources.py** `load_sources()` parses YAML, validates required keys, **filters to only `collector == "rss"`** (line 53). Unknown/malformed entries logged+skipped.
- **cli.py** `collect()` builds ONE `RssCollector`, loops ALL sources through it, dedups, upserts, classifies today's items via hybrid filter, renders markdown.
- **Item** (`storage/models.py`): frozen — `id,title,url,source,source_priority,category,published_at,collected_at,summary,raw`. **NO numeric score field.**
- **dedup.py**: `canonicalize_url` (strips utm_/tracking, lowercases, drops fragment/default-port/trailing-slash), `item_id=sha256(canonical_url)`, `title_hash` (lowercased, punctuation-stripped). `dedup_batch`: collapse by id, then by title_hash; `_wins` = lowest priority int, then earliest published, then smallest id.
- **db.py**: schema has `items` (+canonical_url, title_hash columns) & `item_significance`. Adding a score column = migration touching `_SCHEMA`, `_INSERT_COLUMNS`/`_SELECT_COLUMNS`, `upsert_items` row tuple, `_row_to_item`.
- **config.py**: frozen `Config.from_env()`, `_int_env`/`_float_env` (fail-safe to default, reject negative). Thresholds belong here as `AIOBS_*`.
- **filter.py** `score()` uses `source_priority` + NOISE_KEYWORDS; roadmap's "score threshold" for the firehose is satisfied by collection-time upvote/points cutoffs — not by a filter change.

## CRITICAL discrepancy

`architecture.md` L111 + its yaml example say `RssCollector` handles JSON APIs (`collector: rss`). NOT implementable: `parse_feed` uses feedparser, which only parses RSS/Atom/JSON-Feed. HF Daily Papers & HN Algolia are bespoke JSON, NOT JSON-Feed → need dedicated JSON parsing. Proposal must reconcile (add JSON collectors; update architecture.md's collector table/example).

## Grounded JSON shapes (verified live 2026-07)

**HF Daily Papers** `GET https://huggingface.co/api/daily_papers` (supports `?date=YYYY-MM-DD`): JSON array; each element `{ title, publishedAt(ISO), summary, numComments, paper:{ id(arxiv id), title, summary, authors[], upvotes(int) } }`. Threshold field = `paper.upvotes`. Canonical URL = `https://huggingface.co/papers/{paper.id}`. `published_at` = top-level `publishedAt`.

**HN Algolia** `GET https://hn.algolia.com/api/v1/search_by_date?query=AI&tags=story&numericFilters=points>N`: `{ hits:[ { title, url(external link, may be null for Ask/Show-HN text posts), points(int), objectID, created_at(ISO), created_at_i(epoch), num_comments, story_text? } ] }`. Threshold field = `points`. HN discussion permalink = `https://news.ycombinator.com/item?id={objectID}`. Server-side `numericFilters=points>N` can pre-filter, but the enforced drop should be collector-side for testability.

## Affected Areas

- `collection/base.py` — no change (Source.`collector` already IS the discriminator; Collector Protocol already fits JSON collectors).
- `collection/sources.py` — STOP filtering to only `rss`; return all valid sources so CLI can dispatch by `collector`.
- `collection/hf_papers.py` (NEW) — pure `parse_hf_papers(bytes, min_upvotes, max_chars)->list[Item]` + `HfPapersCollector`.
- `collection/hn_algolia.py` (NEW) — pure `parse_hn_algolia(bytes, min_points, max_chars)->list[Item]` + `HnAlgoliaCollector`.
- `cli.py` — build a `{collector_name: Collector}` dispatch map; per source pick collector, unknown→log+skip. Reuse the single `HttpxFetcher`.
- `config.py` — `AIOBS_HF_MIN_UPVOTES` (default e.g. 5) + `AIOBS_HN_MIN_POINTS` (default e.g. 30) via `_int_env`.
- `sources.yaml` — add HF (`collector: hf_papers`, category research, priority 1) + HN (`collector: hn_algolia`, category community, priority 1) + P2 RSS feeds (config-only).
- Tests: `tests/unit/test_hf_papers.py`, `test_hn_algolia.py` (fixtures: valid, below-threshold dropped, malformed→[], null-url HN fallback, missing fields). Update `test_sources.py` (no longer filters non-rss). Extend integration wiring. Strict TDD: `uv run pytest`, `uv run ruff check .`.

## Approaches — collector design

| Approach | Pros | Cons | Effort |
|---|---|---|---|
| A. Two dedicated collectors (HfPapersCollector, HnAlgoliaCollector), each a pure `parse_*` fn + thin collector, sharing HttpxFetcher & Collector Protocol | Matches existing `parse_feed` pattern exactly; each shape explicit & readable; trivially table-testable; null-url/upvotes edge cases handled per-source; no config indirection | Two small new modules | **Low-Med** |
| B. One generic JsonCollector w/ per-source field-mapping (jsonpath) config in sources.yaml | Single module; "config not code" | Field-map config is complex/opaque; HF nesting + URL construction + HN permalink/null-url fallback don't reduce to a clean generic map; harder to test; over-engineered for 2 sources | Med-High |
| C. Force into RssCollector per architecture.md | Matches (stale) doc | Impossible — feedparser can't parse these JSON schemas | N/A |

## Approaches — score persistence

| Approach | Pros | Cons | Effort |
|---|---|---|---|
| 1. Threshold at collection, DO NOT add `Item.score`; upvotes/points already retained inside `raw` JSON | Keeps slice tight; zero storage migration; future hybrid-filter can read score from `raw` if ever needed; satisfies roadmap | Score not first-class/queryable yet | **Low** |
| 2. Add `Item.score` column now | Score queryable; filter could use it directly | Storage migration across models/db; scope creep; filter change is explicitly OUT of scope this slice | Med |

## Recommendation

**Approach A + Score-Approach 1.** Two dedicated JSON collectors (`HfPapersCollector`, `HnAlgoliaCollector`), each with a pure `parse_*` function mirroring `parse_feed`, sharing the existing `HttpxFetcher` and `Collector` Protocol. **Thresholding inside the collector** (drop below cutoff before returning), cutoffs from `config.py` (`AIOBS_HF_MIN_UPVOTES`, `AIOBS_HN_MIN_POINTS`). **No `Item.score` column** — the numeric score survives in `raw` for a future filter enhancement, keeping this slice migration-free. `load_sources` returns all valid sources; **CLI dispatches by `source.collector`** via a small map, unknown→log+skip. P2 feeds are pure `sources.yaml` additions reusing `RssCollector`.

**Canonical URL / dedup decisions:**
- HN: use external `url` as canonical when present (so an HN story dedups against the primary feed via canonical URL; title_hash is the 2nd safety net). Fall back to the HN permalink when `url` is null (Ask/Show-HN). HN permalink stays in `raw`.
- HF: canonical = `https://huggingface.co/papers/{id}`. Won't URL-dedup vs arXiv RSS, but WILL title_hash-dedup; HF (P1) wins over arXiv (P2) on the tie rule — desirable.

## Open questions for proposal

1. Exact P2 feed set to add (candidates from source-selection Tier 1-6 P2). Recommend a focused subset, not all.
2. Default threshold values: HN points>30 (source-selection example), HF upvotes ~5 (expose via env).
3. Whether to also embed `numericFilters=points>N` in the HN source URL (payload reduction) in addition to the authoritative collector-side drop.
4. Discriminator naming: `hf_papers`/`hn_algolia` (explicit) vs generic `api`. Recommend explicit.
5. Should the propose phase also fix architecture.md L111/example to reflect dedicated JSON collectors? (doc drift).

## Risks

- Architecture.md drift (JSON-via-RssCollector claim is false) may mislead implementers — call it out.
- Live API shape drift (HF nested `paper.upvotes`, HN null `url`) — pin behavior with fixtures; `parse_*` must never raise.
- Threshold too aggressive → empty firehose; too loose → noise. Must be env-tunable.
- HN external-url dedup could suppress a story where the discussion itself is the point — minor; permalink retained in raw.

## Ready for Proposal

Yes. Recommend Approach A + no-score-column.
