# Tasks: Summary Normalization

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300-350 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Config + text.py + rss.py wiring, full test suite green | PR 1 | `uv run pytest tests/unit/test_text.py tests/unit/test_config.py tests/unit/test_rss.py -q` | `uv run python -m ai_observatory.cli collect` against offline fixtures (no network) | Revert `text.py`, `config.py`, `rss.py`, `cli.py` diffs; no schema/migration touched |

## Phase 1: Config (spec: collect-cli / Config Wiring)

- [x] 1.1 RED — `tests/unit/test_config.py`: add cases — default `summary_max_chars == 500`; `AIOBS_SUMMARY_MAX_CHARS=250` override; invalid (`"abc"`) → 500; negative (`"-5"`) → 500; `"0"` → 0.
- [x] 1.2 GREEN — `src/ai_observatory/config.py`: add `_DEFAULT_SUMMARY_MAX_CHARS = 500`, `summary_max_chars: int` field, wire via existing `_int_env("AIOBS_SUMMARY_MAX_CHARS", _DEFAULT_SUMMARY_MAX_CHARS)` in `from_env`.

## Phase 2: normalize_summary (spec: feed-collection / Feed Parsing — HTML/paragraph/truncation scenarios)

- [x] 2.1 RED — create `tests/unit/test_text.py` with failing cases: no-tags passthrough; entity decode; first-paragraph drops trailing Tags/Via block; multi-paragraph body truncated with ellipsis; `max_chars=0` → `""`; `max_chars < len("…")` → `""`; whitespace-only → `""`; non-Latin text; broken/nested tags tolerated; already-short text passthrough.
- [x] 2.2 GREEN — create `src/ai_observatory/collection/text.py`: `normalize_summary(raw_summary: str, max_chars: int) -> str` per design's 5-step order (guard `max_chars<=0`; first-paragraph on raw string via `</p>` or blank-line; tolerant `HTMLParser` subclass with `convert_charrefs=True` to strip tags/decode entities; whitespace collapse + strip; ellipsis-aware truncate).

## Phase 3: Wire into rss.py (spec: feed-collection — HTML entry, Tags/Via, long body, empty description, zero max_chars scenarios)

- [x] 3.1 RED — create fixtures `tests/fixtures/feed_html_summary.xml`, `feed_empty_summary.xml`, `feed_long_summary.xml`; add failing `test_rss.py` assertions calling `parse_feed(data, max_chars)` against each; add regression assertion `feed_valid.xml` `items[1].summary == "Summary of the second item."`.
- [x] 3.2 GREEN — `src/ai_observatory/collection/rss.py`: change `parse_feed(data: bytes, max_chars: int)`, call `normalize_summary(summary, max_chars)` at line 124 in place of raw summary; leave `raw` (line 127) untouched.
- [x] 3.3 GREEN — `rss.py`: `RssCollector.__init__(self, fetcher, summary_max_chars: int)`, store `self._summary_max_chars`; `collect()` calls `parse_feed(raw_bytes, self._summary_max_chars)`.
- [x] 3.4 GREEN — update existing constructor call sites: `tests/unit/test_rss.py:110,121` and `tests/integration/test_collect_integration.py:69-70` to pass `summary_max_chars`.
- [x] 3.5 GREEN — `src/ai_observatory/cli.py:56` (sole production call site): `RssCollector(fetcher, config.summary_max_chars)`.

## Phase 4: Spec Alignment (spec: daily-record / Item Line Format)

- [x] 4.1 Confirm no code change needed: `src/ai_observatory/records.py:67` (`if item.summary:`) already omits empty summaries post-normalization; existing render test still passes unchanged.

## Phase 5: Verification

- [x] 5.1 Run `uv run pytest`; report exact pass count (baseline 62 + new tests, 0 failures). Result: 81 passed (62 baseline + 19 new: 5 config + 10 text + 4 rss/integration).
- [x] 5.2 Run `uv run ruff check .`; report 0 errors (fix and re-run if any). Result: All checks passed.
