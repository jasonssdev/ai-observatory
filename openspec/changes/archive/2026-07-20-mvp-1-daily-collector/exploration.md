# Exploration: MVP-1 "daily record collector"

Scope investigation for the first validatable vertical slice per `docs/roadmap.md`.
Grounded in `docs/{roadmap,architecture,vision,source-selection}.md`, `pyproject.toml`, and the current scaffold.

## Current State (scaffold reality)

- Only production file: `src/ai_observatory/__init__.py` containing a `main()` print stub. No collection/storage/synthesis modules exist yet.
- No `tests/` directory yet. pytest is configured in `pyproject.toml` (`testpaths=["tests"]`, `pythonpath=["src"]`, `--strict-markers --strict-config`).
- Deps already chosen: `feedparser>=6.0.12`, `httpx>=0.28.1`, `pyyaml>=6.0.3`, `typer>=0.27.0`. Dev: `pytest>=9.1.1`, `ruff>=0.15.22`. Python `>=3.13`. Build backend `uv_build`.
- Entry point: `[project.scripts] ai-observatory = "ai_observatory:main"` — currently a stub, must become the typer `collect` command (preserve this entry-point contract).
- SDD backend: openspec hybrid mode, `strict_tdd: true`. Test runner `uv run pytest`; lint `uv run ruff check .`; format `uv run ruff format .`. No type checker configured.
- No new runtime deps needed: SQLite via stdlib `sqlite3`; feed fetch/parse via httpx + feedparser; config via pyyaml; CLI via typer.

## MVP-1 Scope — IN

- `config.py` (paths: data dir, DB path, `sources.yaml` path, User-Agent string), `cli.py` with a `collect` command (typer).
- `sources.yaml` with ~8-10 P1 RSS/Atom feeds.
- `RssCollector` + deduplication (canonical URL + title hash).
- SQLite store (`items` table) as source of truth + a Markdown daily record `data/records/<date>.md` grouped by category/priority.
- Tests for collector, dedup, storage: success path, malformed feed, duplicate item (per `AGENTS.md`).

## MVP-1 Scope — OUT (explicit non-goals)

- No LLM / no Ollama, no filtering (record shows EVERYTHING collected — raw dump is acceptable for MVP-1).
- No weekly briefing / no synthesis layer.
- No scheduling / no launchd (manual `collect` only).
- No JSON-API sources (HF Daily Papers, HN Algolia), no bridged/RSSHub sources (Anthropic, Meta, etc.), no Apify/X.
- No full-text article fetching (feed summaries only). No web UI. No `.env`/secrets needed (no credentials in this slice).

## Candidate P1 RSS/Atom feeds (from source-selection.md, excluding API + bridged)

Strict P1 & RSS/Atom = 8 feeds: OpenAI (`openai.com/news/rss.xml`), Google DeepMind (`deepmind.google/blog/rss.xml`), Import AI (`importai.substack.com/feed`), Last Week in AI (`lastweekin.ai/feed`), Interconnects (`interconnects.ai/feed`), Simon Willison (`simonwillison.net/atom/everything/`, Atom), TLDR AI (`tldr.tech/api/rss/ai`), Semianalysis (`semianalysis.com/feed`).

Note: roadmap's example list also names "Google AI" which is P2 (`blog.google/technology/ai/rss/`). To reach the "~8-10" target the proposal may include 1-2 high-signal P2 RSS feeds. **DECISION for proposal:** exactly which feeds and whether to admit P2s to hit ~10.

## Gap Analysis (current vs. MVP-1 need)

Needed modules not present: `collection/{base.py,rss.py,sources.py,dedup.py}`, `storage/{db.py,records.py,models.py}`, `config.py`, `cli.py`, `sources.yaml`, `tests/`. Entry point must be rewired from stub `main()` to typer app while keeping `ai_observatory:main` working. Architecture (`docs/architecture.md`) already prescribes the module layout, Item schema, and Collector Protocol — MVP-1 is a strict subset (RssCollector only, no synthesis).

## Item schema (from architecture.md, MVP-1 subset)

`id` (hash of canonical url, dedup key), `title`, `url` (canonical, tracking stripped), `source`, `source_priority` (int), `category` (lab/research/newsletter/news/tooling/community), `published_at` (UTC), `collected_at` (UTC), `summary` (feed text), `raw` (json). SQLite `items` keyed by `id`, indexed on `published_at` and `source_priority`.

## Approaches

### 1. Fetch+parse: httpx fetch → feedparser parse-from-bytes (RECOMMENDED)

- `httpx.get(url, headers={User-Agent}, timeout, follow_redirects)` then `feedparser.parse(resp.content)`.
- **Pros:** explicit timeout + UA control; httpx already a dependency (currently unused); testable under strict TDD via mounted httpx `MockTransport` or by passing raw feed bytes to a pure parse function (no network in tests); clean fetch/parse seam (hexagonal port boundary); reuses httpx for MVP-2's JSON-API collector. httpx auto-decodes gzip.
- **Cons:** slightly more code than feedparser's built-in fetch; must set Accept-Encoding/UA explicitly.
- **Effort:** Low-Medium.

### 2. feedparser-only (`feedparser.parse(url, agent=UA)`)

- **Pros:** least code; feedparser handles gzip/redirects/etag/last-modified transparently.
- **Cons:** network fetch buried inside parse → hard to unit-test without hitting the wire or heavy monkeypatching; weaker timeout control; leaves httpx unused; poorer seam for future API collector. Conflicts with strict TDD ergonomics.
- **Effort:** Low.

### 3. httpx only, hand-roll RSS/Atom parsing

- **Rejected:** reinvents feedparser, brittle across RSS/Atom variants, high effort, no benefit.
- **Effort:** High.

**Storage:** stdlib `sqlite3`, `items` table, idempotent upsert (`INSERT ... ON CONFLICT(id) DO NOTHING` / `INSERT OR IGNORE`) so re-runs never duplicate. Markdown record fully regenerated from DB for the date each run (idempotent view). No new dependency.

**Dedup:** pure function(s) — canonicalize URL (strip fragment + UTM/tracking query params, normalize host/scheme/trailing slash) → sha256 → `id` (primary/persistent dedup across runs via DB PK). Secondary title-hash (lowercased, punctuation/whitespace-normalized) to catch the same story arriving via different feeds with different URLs. Pure functions are ideal for strict-TDD unit coverage.

## Recommendation

Approach 1 (httpx fetch + feedparser parse) with stdlib sqlite3 storage and pure-function dedup. It is the most testable under strict TDD (RED-GREEN with feed-bytes fixtures and a mocked httpx transport, zero network in tests), uses only already-chosen deps, honors the architecture's fetch→parse→normalize→store→render pipeline, and establishes the seam MVP-2 needs. Non-fatal per-source error handling (dead feed / malformed XML / timeout is logged and skipped) is a hard requirement from vision + architecture.

## Open Questions / Decisions for the proposal phase

1. **Daily-record semantics:** does `<date>.md` = the run date containing everything collected that run (new-since-last), or items filtered by `published_at` calendar day? This defines idempotency and catch-up behavior. (Recommend: file keyed by run date; record = items with `published_at` on that date, regenerated from DB — but must be decided.)
2. **Markdown layout:** grouping order (category then priority? priority then category?), sort within group, which Item fields render, and confirm full-regeneration-from-DB on every run.
3. **Dedup precision:** exact URL canonicalization rules (which query params are noise vs. meaningful — over-stripping can merge distinct items); title-hash normalization; precedence when URL-dedup and title-dedup disagree, and which source "wins" (highest priority?).
4. **sources.yaml shape:** confirm fields `{name, collector, url, category, priority}`; MVP-1 loads only `collector: rss`; finalize the exact 8-10 feeds and whether any P2 RSS is admitted to reach ~10.
5. **Scheduling boundary:** confirm MVP-1 is manual `collect` only (no launchd) — settled by roadmap, restate as a non-goal.
6. **Missing/naive published_at:** default when a feed omits dates; UTC normalization of tz-aware and naive datetimes.
7. **raw storage:** store original feed entry as JSON text column for traceability/reprocessing.
8. **Entry point:** reconcile `[project.scripts] ai_observatory = "ai_observatory:main"` with a typer app (main() invokes the typer app, or point script at the typer callback).
9. **config.py:** hardcoded defaults vs. env overrides for data dir / DB path / UA (no secrets required in MVP-1).

## Risks / Unknowns

- Network reliability: feeds go down / rate-limit / return malformed XML — single broken source must never fail the run (log+skip). Malformed-feed test is mandatory.
- Feed date inconsistency: some feeds omit or mis-format published dates → ambiguous "daily" grouping and idempotency edge cases.
- URL canonicalization edge cases: aggressive param stripping may collapse distinct items; too little leaves duplicates. Needs careful, tested rules.
- Strict TDD + network: tests must inject bytes / mock httpx transport; no live network in CI. Approach 1 makes this natural; approach 2 fights it.
- Idempotency depends on stable `id` (stable canonical-URL hash) + DB upsert + full Markdown regeneration — any instability reintroduces duplicates.
- User-Agent requirement: several outlets reject empty/default UAs (set a real UA anyway).
- Entry-point mismatch risk if typer wiring drops the `ai_observatory:main` contract.

## Testability implications (strict TDD active — no code written this phase)

- Fetch/parse seam: pure `parse_feed(bytes) -> list[Item]`, and a fetch adapter mockable via httpx `MockTransport`. Fixtures: valid feed, malformed XML, feed with duplicate/near-duplicate items.
- Dedup: pure functions (`canonicalize_url`, `title_hash`, item `id`) → straightforward unit tests.
- Storage: temp-file or `:memory:` sqlite; assert upsert idempotency and dedup persistence; assert Markdown render from a known item set.
- Required cases per `AGENTS.md`/roadmap: success, malformed feed, duplicate item.

## Ready for Proposal

Yes. Scope is well-bounded (roadmap MVP-1 + architecture subset). Proceed to `sdd-propose` to resolve the 9 open decisions above (chiefly daily-record semantics, dedup rules, and the exact feed list).
