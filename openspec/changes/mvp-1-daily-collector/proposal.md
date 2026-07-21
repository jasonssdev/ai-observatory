# Proposal: MVP-1 Daily Record Collector

## Intent

Stop checking AI feeds by hand. One command (`collect`) fetches 9 P1/P2 RSS/Atom
feeds, normalizes and deduplicates them, persists to SQLite (source of truth), and
renders a readable Markdown daily record. First validatable vertical slice per
`docs/roadmap.md` MVP-1. No LLM, no filtering — it captures everything collected.

## Scope

### In Scope
- `config.py` (paths + User-Agent, env-overridable), `cli.py` `collect` command (typer).
- `sources.yaml` with 9 feeds (8 strict P1 RSS/Atom + Google AI P2, roadmap-mandated).
- `collection/`: `base.py` (Collector Protocol, Source), `rss.py` (httpx fetch + pure `parse_feed(bytes)`), `sources.py` (loader), `dedup.py` (pure functions).
- `storage/`: `models.py` (Item), `db.py` (SQLite `items`, idempotent upsert), `records.py` (Markdown writer).
- Non-fatal per-source errors (dead feed / malformed XML / timeout logged + skipped).
- Tests: success, malformed feed, duplicate item, idempotent re-run, missing-date default.

### Out of Scope (non-goals)
- No LLM/Ollama, no filtering, no weekly briefing/synthesis.
- **No scheduling** (launchd/cron) — manual `collect` only.
- No JSON-API sources (HF, HN Algolia), no bridged/RSSHub, no Apify/X, no full-text fetch, no web UI, no `.env`/secrets.

## Capabilities

### New Capabilities
- `feed-collection`: fetch + parse RSS/Atom into normalized Items; non-fatal per-source failure.
- `item-deduplication`: canonical-URL id + title-hash dedup with source-priority tie-break.
- `item-storage`: SQLite `items` table, idempotent upsert, query-by-date.
- `daily-record`: Markdown record grouped by category/priority, regenerated from DB.
- `collect-cli`: `collect` command + config wiring (preserves `ai_observatory:main`).

### Modified Capabilities
None.

## Approach

Exploration **Approach 1**: httpx fetch → `feedparser.parse(bytes)` → normalize → dedup → stdlib `sqlite3` upsert → regenerate Markdown. Pure fetch/parse seam enables strict-TDD with feed-byte fixtures + httpx `MockTransport` (zero network in tests). Only already-chosen deps.

### Key Decisions (resolves 9 open items)
| # | Decision |
|---|----------|
| 1 | **Daily-record semantics**: group by `published_at` UTC calendar day. DB is source of truth (idempotent upsert on `id`). Each run regenerates the Markdown file for every published-date present in the collected batch (plus run's UTC date). Re-runs never duplicate. |
| 2 | **Markdown layout**: full regeneration from DB per run. Group by category (lab, research, newsletter, news, tooling, community); within group sort by `source_priority` asc then `published_at` desc. Render `- [title](url) — source (Pn) · HH:MM UTC` + summary. Header with date + item count. |
| 3 | **Dedup**: canonicalize URL (lowercase scheme/host, drop fragment + default port + trailing slash, strip `utm_*,ref,ref_src,fbclid,gclid,mc_cid,mc_eid,igshid,source,cmpid`; keep other params). `id = sha256(canonical_url)` = DB PK (persistent dedup). Secondary `title_hash` (lowercased, punctuation/whitespace-normalized, sha256) catches same story via different URLs within a run; on collision keep highest-priority source (lowest int), tie-break earliest `published_at` then lexical `id`. |
| 4 | **sources.yaml**: fields `{name, collector, url, category, priority}`; MVP-1 loads only `collector: rss`. Final 9 (roadmap.md line 22): OpenAI, DeepMind, Import AI, Last Week in AI, Interconnects, Simon Willison, TLDR AI, Semianalysis (P1) + Google AI (P2, roadmap-mandated). Sits in the roadmap "~8-10" target; not padded to 10. |
| 5 | **Scheduling**: manual `collect` only — restated non-goal. |
| 6 | **published_at**: tz-aware → UTC; naive → assume UTC; missing/unparseable → default to `collected_at`. Stored ISO-8601 UTC. |
| 7 | **raw**: store original entry as JSON text (`raw` column, stdlib `json`) for traceability/reprocessing. |
| 8 | **Entry point**: keep `[project.scripts] ai-observatory = "ai_observatory:main"`; `main()` becomes thin wrapper invoking the typer `app` from `cli.py`. |
| 9 | **config.py**: hardcoded defaults with `AIOBS_*` env overrides (`DATA_DIR=./data`, `DB_PATH=data/observatory.db`, `RECORDS_DIR=data/records`, `SOURCES_PATH=./sources.yaml`, real `USER_AGENT`). No secrets. |

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/__init__.py` | Modified | `main()` → wrapper calling typer app. |
| `src/ai_observatory/{config,cli}.py` | New | Config + `collect` command. |
| `src/ai_observatory/collection/*` | New | base, rss, sources, dedup. |
| `src/ai_observatory/storage/*` | New | models, db, records. |
| `sources.yaml` | New | 10-feed source list. |
| `tests/**` | New | collector, dedup, storage, cli. |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Aggressive URL param stripping merges distinct items | Med | Conservative strip-list; keep unknown params; unit-tested rules. |
| Feeds omit/misformat dates → ambiguous grouping | Med | Default to `collected_at`; UTC normalization tested. |
| Single broken feed fails run | Med | Per-source try/except, log + skip; malformed-feed test mandatory. |
| Entry-point contract dropped | Low | Keep `main()` wrapper; smoke test `collect`. |
| Idempotency regression (unstable id) | Low | Stable canonical-URL hash + `INSERT OR IGNORE` + full Markdown regen; re-run test. |

## Rollback Plan
New feature slice; no existing behavior depends on it. Revert the change branch; restore stub `main()`. `data/` is gitignored — delete `data/observatory.db` and `data/records/` to reset state. No migrations to unwind.

## Dependencies
None new. feedparser, httpx, pyyaml, typer, stdlib `sqlite3`/`json` (all already chosen).

## Success Criteria
- [ ] `uv run ai-observatory collect` produces `data/records/<YYYY-MM-DD>.md` from live feeds.
- [ ] Record is deduplicated, category-grouped, links resolve, items sorted by priority.
- [ ] Re-running the same day adds no duplicates (idempotent DB + regenerated Markdown).
- [ ] A malformed/dead feed is logged and skipped without failing the run.
- [ ] Tests cover success, malformed feed, duplicate item, idempotent re-run, missing-date default; `uv run pytest` green.
