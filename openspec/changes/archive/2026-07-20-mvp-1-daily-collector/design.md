# Design: MVP-1 Daily Record Collector

## Technical Approach

Approach 1 (locked): `httpx` fetch → `feedparser.parse(bytes)` → normalize → pure-function dedup → stdlib `sqlite3` upsert → regenerate Markdown from DB. The pipeline is split at a **fetch/parse seam**: I/O (network, disk) lives in thin injectable adapters; everything else is pure functions over bytes/dataclasses. This is a strict subset of `docs/architecture.md` (collection → storage, no synthesis). Strict TDD: every unit is a pure function or takes an injected adapter, so tests use feed-byte fixtures + `httpx.MockTransport` + `:memory:` sqlite — zero network, zero temp files required.

## Architecture Decisions

### Decision: Fetch/parse seam as the testability boundary
| Option | Tradeoff | Decision |
|--------|----------|----------|
| One `collect()` that fetches+parses | Simplest; untestable without network | Rejected |
| Pure `parse_feed(bytes)->list[Item]` + injected `Fetcher` adapter | One extra seam; fully unit-testable | **Chosen** |

**Rationale**: `parse_feed` is deterministic over fixture bytes; `RssCollector` takes a `Fetcher` (default wraps `httpx.Client`, tests pass `MockTransport`). No network in the unit suite.

### Decision: Dedup as pure functions, id = sha256(canonical_url)
**Choice**: `canonicalize_url`, `title_hash`, `item_id`, `dedup_batch` — all pure. Persistent dedup via DB PK `id`; in-run cross-URL dedup via `title_hash`.
**Alternatives**: DB UNIQUE on url (fragile to tracking params); fuzzy title match (non-deterministic). **Rejected.**
**Rationale**: Stable hash → idempotent `INSERT OR IGNORE`. Pure functions are trivially table-tested.

### Decision: DB is source of truth; Markdown fully regenerated
**Choice**: Upsert items, then re-render `records/<date>.md` for each published-date in the batch (+ run's UTC date) by querying the DB.
**Alternatives**: Append to Markdown (drifts, duplicates on re-run). **Rejected.**
**Rationale**: Idempotent re-runs, Markdown is a disposable view.

### Decision: `main()` as thin wrapper over typer app
**Choice**: `cli.py` owns `app = typer.Typer()` + `collect`; `__init__.main()` calls `app()`. Preserves `ai-observatory = "ai_observatory:main"`.
**Rationale**: Keeps the entry-point contract while centralizing CLI in `cli.py`.

## Data Flow

```
sources.yaml ─▶ load_sources() ─▶ [Source]
                                     │
         Fetcher.get(url) ─▶ bytes ─▶ parse_feed(bytes) ─▶ [Item]  (per source, try/except log+skip)
                                     │
                 dedup_batch([Item]) ─▶ [Item]
                                     │
              db.upsert_items() ─▶ SQLite (source of truth)
                                     │
   for date in batch: records.write(db.items_for_date(date)) ─▶ data/records/<date>.md
```

## File Changes
| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/__init__.py` | Modify | `main()` → `from .cli import app; app()`. |
| `src/ai_observatory/config.py` | Create | Frozen `Config` from `AIOBS_*` env + defaults. |
| `src/ai_observatory/cli.py` | Create | Typer `app`, `collect` command wiring config→collectors→db→records. |
| `src/ai_observatory/collection/base.py` | Create | `Source` dataclass, `Collector`/`Fetcher` Protocols. |
| `src/ai_observatory/collection/rss.py` | Create | `HttpxFetcher`, `parse_feed(bytes)`, `RssCollector(fetcher)`. |
| `src/ai_observatory/collection/sources.py` | Create | `load_sources(path)`; filter `collector=="rss"`. |
| `src/ai_observatory/collection/dedup.py` | Create | Pure dedup functions. |
| `src/ai_observatory/storage/models.py` | Create | `Item` dataclass. |
| `src/ai_observatory/storage/db.py` | Create | `connect`, schema DDL, `upsert_items`, `items_for_date`. |
| `src/ai_observatory/storage/records.py` | Create | `render_markdown(items, date)`, `write_record`. |
| `sources.yaml` | Create | 9 feeds (8 P1 + Google AI P2). |
| `tests/**` | Create | Fixtures + unit/integration tests. |

## Interfaces / Contracts

```python
# storage/models.py
@dataclass(frozen=True)
class Item:
    id: str; title: str; url: str; source: str
    source_priority: int; category: str
    published_at: datetime; collected_at: datetime  # UTC, tz-aware
    summary: str; raw: str  # raw = json.dumps(entry)

# collection/base.py
@dataclass(frozen=True)
class Source: name: str; collector: str; url: str; category: str; priority: int
class Fetcher(Protocol):
    def get(self, url: str) -> bytes: ...
class Collector(Protocol):
    def collect(self, source: Source) -> list[Item]: ...

# collection/dedup.py  (all pure)
def canonicalize_url(url: str) -> str        # lower scheme/host; drop fragment,
    # default port, trailing slash; strip utm_*,ref,ref_src,fbclid,gclid,
    # mc_cid,mc_eid,igshid,source,cmpid; keep other params
def title_hash(title: str) -> str            # lower, strip punct/collapse ws, sha256
def item_id(canonical_url: str) -> str       # sha256 hex
def dedup_batch(items: list[Item]) -> list[Item]
    # 1) dedup by id  2) collapse same title_hash → keep lowest priority,
    #    tie earliest published_at, then lexical id
```

**SQLite `items`**: `id TEXT PRIMARY KEY, title, url, source, source_priority INT, category, published_at TEXT, collected_at TEXT, summary, raw TEXT`. Indexes: `idx_published_at(published_at)`, `idx_source_priority(source_priority)`. Write = `INSERT OR IGNORE`.

**Markdown**: header `# <date> (<n> items)`; group by category (lab, research, newsletter, news, tooling, community); within group sort `source_priority` asc, `published_at` desc; line `- [title](url) — source (Pn) · HH:MM UTC` + summary.

**Config defaults** (`AIOBS_*` override): `DATA_DIR=./data`, `DB_PATH=data/observatory.db`, `RECORDS_DIR=data/records`, `SOURCES_PATH=./sources.yaml`, real `USER_AGENT`.

**published_at**: tz-aware→UTC; naive→assume UTC; missing/unparseable→`collected_at`.

## Testing Strategy
| Layer | What | Approach |
|-------|------|----------|
| Unit | `canonicalize_url`, `title_hash`, `item_id`, `dedup_batch` | Table tests, pure |
| Unit | `parse_feed` (success, malformed, missing-date) | Byte fixtures in `tests/fixtures/` |
| Unit | `RssCollector` per-source error | `MockTransport` raising → log+skip |
| Unit | `render_markdown` | Fixed `Item` list → asserted string |
| Integration | `upsert_items`/`items_for_date`, idempotent re-run | `sqlite3.connect(":memory:")` |
| Smoke | `collect` wiring, `main()` entry point | Typer `CliRunner`, mocked fetcher |

Seams: `Fetcher` injected into `RssCollector`; `sqlite3.Connection` injected into db functions; `parse_feed`/dedup/render take plain values.

## Threat Matrix
N/A — no shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Network fetch is a read of trusted config-listed feed URLs via `httpx` (no shell), with per-source try/except log+skip. No user-supplied URLs.

## Migration / Rollout
No migration. Fresh schema created on first `connect` (`CREATE TABLE IF NOT EXISTS`). `data/` gitignored; delete DB + records to reset.

## Open Questions
None blocking. (feedparser field mapping — `entry.link`, `entry.title`, `entry.summary`, `entry.published_parsed` — verified against feedparser 6.x during implementation.)
