# Design: Summary Normalization

## Technical Approach

Introduce one pure module `collection/text.py` exposing
`normalize_summary(raw_summary: str, max_chars: int) -> str`. `parse_feed`
calls it at rss.py:124, replacing the verbatim `summary`. `max_chars` is
threaded explicitly from `Config` → `RssCollector` → `parse_feed`, so
`parse_feed` stays pure (no `config` import). Stdlib only (`html.parser`,
`re`). Mirrors the existing `record_window_days` config precedent.

## Architecture Decisions

### Decision: Pure helper in a new `text.py`, not inline in `parse_feed`

**Choice**: Separate `normalize_summary` function.
**Alternatives**: Inline logic in `parse_feed`; a class.
**Rationale**: Matches the codebase's pure-function seam style
(`_normalize_published_at`); unit-testable in isolation without XML fixtures.

### Decision: Tolerant `HTMLParser` subclass for tag stripping

**Choice**: `html.parser.HTMLParser` subclass, `convert_charrefs=True`,
collecting `handle_data` text; never raises on malformed/nested tags.
**Alternatives**: Regex tag stripping (fragile, unsafe on nested/broken
markup); add `beautifulsoup4`/`lxml` (new dependency, out of scope).
**Rationale**: Stdlib, tolerant, single-pass entity decode — matches
`parse_feed`'s no-raise ethos (rss.py:113). `convert_charrefs=True` decodes
entities exactly once (avoids double-unescape).

### Decision: Explicit `max_chars` threading (required params)

**Choice**: `parse_feed(data, max_chars)` and
`RssCollector(fetcher, summary_max_chars)` — both required, no `config`
import in the pure layer.
**Alternatives**: `parse_feed` reads `Config` internally (breaks purity);
module-level global.
**Rationale**: Keeps `parse_feed` a pure `bytes → list[Item]` transform.
Single production call site (cli.py:56) supplies `config.summary_max_chars`.

## Algorithm (exact order)

`normalize_summary(raw_summary, max_chars)`:
1. **Guard**: `max_chars <= 0` → return `""`.
2. **First paragraph** (on the RAW string, before tag removal, so paragraph
   structure survives):
   - if `</p>` present (case-insensitive) → substring up to first `</p>`;
   - elif a blank line (`\r?\n\s*\r?\n`) present → text before first blank line;
   - else → whole string.
3. **Strip tags + unescape**: feed the fragment to the `HTMLParser` subclass;
   concatenate `handle_data` chunks. Entities decoded once via
   `convert_charrefs=True`.
4. **Collapse whitespace**: `re.sub(r"\s+", " ", text).strip()`. Whitespace-only
   → `""`.
5. **Truncate** (`ELLIPSIS = "…"`, `len == 1`): if `len(result) <= max_chars`
   → return as-is. Else if `max_chars < len(ELLIPSIS)` → `""` (underflow guard).
   Else `keep = max_chars - len(ELLIPSIS)`;
   `return result[:keep].rstrip() + ELLIPSIS`. Total length ≤ `max_chars`.

Dropping trailing "Tags: …/Via: …" lines is a consequence of step 2 when those
sit in later paragraphs/blank-line-separated blocks; no dedicated stripping.

## Data Flow

    Config.summary_max_chars ─→ RssCollector(fetcher, summary_max_chars)
                                        │  collect()
                                        ▼
    raw bytes ─→ parse_feed(data, max_chars) ─→ normalize_summary(raw, max_chars)
                                        │
                                        └─→ Item.summary (clean)   Item.raw (untouched)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/collection/text.py` | Create | Pure `normalize_summary` + tolerant `HTMLParser` stripper |
| `src/ai_observatory/collection/rss.py` | Modify | `parse_feed(data, max_chars)`; call at :124; `RssCollector(fetcher, summary_max_chars)`; call `parse_feed(raw_bytes, self._summary_max_chars)` at :165. `raw` (:127) untouched |
| `src/ai_observatory/config.py` | Modify | `_DEFAULT_SUMMARY_MAX_CHARS = 500`; `summary_max_chars: int` field; `_int_env("AIOBS_SUMMARY_MAX_CHARS", _DEFAULT_SUMMARY_MAX_CHARS)` in `from_env` — same edit shape as `record_window_days` (config.py:15,37,47-49) |
| `src/ai_observatory/cli.py` | Modify | Line 56: `RssCollector(fetcher, config.summary_max_chars)` (sole production call site) |
| `tests/fixtures/feed_html_summary.xml` | Create | HTML tags + entities + trailing Tags/Via |
| `tests/fixtures/feed_empty_summary.xml` | Create | Whitespace-only description |
| `tests/fixtures/feed_long_summary.xml` | Create | Description exceeding a small test cap |
| `tests/unit/test_text.py` | Create | Pure unit tests for `normalize_summary` |
| `tests/unit/test_rss.py` | Modify | Update `parse_feed`/`RssCollector` call sites; add fixture assertions |
| `tests/unit/test_config.py` | Modify | `summary_max_chars` default/override/invalid |
| `tests/integration/test_collect_integration.py` | Modify | `RssCollector` constructor now takes `summary_max_chars` |

## Interfaces / Contracts

```python
def normalize_summary(raw_summary: str, max_chars: int) -> str: ...
def parse_feed(data: bytes, max_chars: int) -> list[Item]: ...
class RssCollector:
    def __init__(self, fetcher: Any, summary_max_chars: int) -> None: ...
```

`_int_env` semantics reused: missing/invalid/negative → 500; `0` is valid
(and, via the `max_chars <= 0` guard, yields `""`).

## Testing Strategy (red-first, offline, no network)

| Layer | What | Approach |
|-------|------|----------|
| Unit `test_text.py` | HTML→no tags; entity decode (`&amp;`→`&`); first paragraph drops Tags/Via; multi-paragraph truncation + ellipsis; `max_chars=0`→`""`; `max_chars < len("…")`→`""`; whitespace-only→`""`; non-Latin text; broken/nested tags tolerated; already-short passthrough | Direct calls to `normalize_summary` |
| Unit `test_rss.py` | `feed_html_summary` → stripped/decoded/first-paragraph; `feed_empty_summary` → `""`; `feed_long_summary` (small `max_chars`) → truncated + `…`; **regression:** `feed_valid.xml` `items[1].summary == "Summary of the second item."` still holds | `parse_feed(bytes, max_chars=…)` on offline fixtures |
| Unit `test_config.py` | default 500; `AIOBS_SUMMARY_MAX_CHARS` override; invalid/negative→500; `0` valid | `Config.from_env` + monkeypatched env |
| Integration | Existing dedup/store behavior unchanged | Update `RssCollector` construction only |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. HTML parsing is stdlib and
bounded; feed size already capped at 10 MB (rss.py:36) and whitespace collapse
uses a linear regex (no ReDoS).

## Migration / Rollout

No migration. `db.py:73` uses `INSERT OR IGNORE` keyed by item id, so existing
rows keep dirty summaries; only newly collected items normalize. Operational
reset: `rm -rf data` then re-collect. `summary TEXT NOT NULL` schema unchanged.
`records.py:67` (`if item.summary:`) already omits empty summaries — the
daily-record clarification documents existing behavior, no code change.

## Open Questions

- None blocking.
