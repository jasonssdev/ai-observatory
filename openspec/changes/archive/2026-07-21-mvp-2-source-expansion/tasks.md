# Tasks: MVP-2 Source Expansion (JSON APIs + P2 feeds)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~480-650 (config.py +15, test_config.py +40, hf_papers.py NEW +100, hn_algolia.py NEW +100, test_hf_papers.py NEW +80, test_hn_algolia.py NEW +90, 3 json fixtures +80, sources.py ~5, test_sources.py +20, cli.py +20, test_collect_integration.py +50, sources.yaml +100, docs/architecture.md +10) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: JSON collectors (hf_papers + hn_algolia + fixtures + unit tests) -> PR 2: config + dispatch + sources.py + sources.yaml (HF/HN/P2) + docs fix + integration tests |
| Delivery strategy | auto-forecast (not a listed enum; treated as auto-chain-equivalent — proceed with first slice, confirm chain strategy) |
| Chain strategy | feature-branch-chain (PR 2 imports `HfPapersCollector`/`HnAlgoliaCollector` from PR 1) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|------------------|--------------------|
| 1 | Pure `parse_hf_papers`/`parse_hn_algolia` + thin never-raise `HfPapersCollector`/`HnAlgoliaCollector` + fixtures | PR 1 (base: tracker/main) | `uv run pytest tests/unit/test_hf_papers.py tests/unit/test_hn_algolia.py -q` | N/A — fixture-driven fake fetcher, zero network | Delete `collection/hf_papers.py`, `collection/hn_algolia.py`, their tests, and the 3 new fixture files; nothing else references them yet |
| 2 | `config.py` thresholds, `sources.py` filter removal, `cli.py` dispatch map, `sources.yaml` HF/HN/P2 entries, `docs/architecture.md` fix, dispatch+dedup integration tests | PR 2 (base: PR 1 branch) | `uv run pytest tests/unit/test_config.py tests/unit/test_sources.py tests/integration/test_collect_integration.py -q` | `uv run ai-observatory collect` against a temp `sources.yaml` + tmp DB with `MockTransport`-backed fetchers for RSS/HF/HN (no live network) | Revert `config.py` fields, `sources.py` filter, `cli.py` dispatch wiring, `sources.yaml` new entries, `docs/architecture.md` edit, and the integration/unit test diffs; PR 1's collectors stay intact and simply unused |

## Phase 1: Config (`config.py`) — Req: Configuration-Driven Thresholds

- [x] 1.1 RED `test_config.py::TestHfMinUpvotes` — unset -> `5`; `AIOBS_HF_MIN_UPVOTES=10` -> `10`; non-integer/negative -> `5`
- [x] 1.2 GREEN `config.py`: `_DEFAULT_HF_MIN_UPVOTES = 5`, `hf_min_upvotes: int` field, `_int_env("AIOBS_HF_MIN_UPVOTES", 5)` in `from_env`
- [x] 1.3 RED `test_config.py::TestHnMinPoints` — unset -> `30`; `AIOBS_HN_MIN_POINTS=50` -> `50`; non-integer/negative -> `30`
- [x] 1.4 GREEN `config.py`: `_DEFAULT_HN_MIN_POINTS = 30`, `hn_min_points: int` field, `_int_env("AIOBS_HN_MIN_POINTS", 30)` in `from_env`

## Phase 2: Fixtures (`tests/fixtures/`)

- [x] 2.1 Create `tests/fixtures/hf_daily_papers.json` — array of papers with nested `paper.upvotes`, including one paper below the default cutoff (`upvotes < 5`)
- [x] 2.2 Create `tests/fixtures/hn_algolia.json` — `hits[]` including one hit with `url: null` and one hit below the default cutoff (`points < 30`)
- [x] 2.3 Create `tests/fixtures/json_malformed.json` — invalid JSON bytes, shared by both collectors' malformed-input tests

## Phase 3: HF collector (`collection/hf_papers.py`, NEW) — Req: HF Daily Papers Parsing / Score Threshold / Failure Isolation

- [x] 3.1 RED `test_hf_papers.py::test_parse_valid_maps_fields` — nested `paper.upvotes`, canonical `url == https://huggingface.co/papers/{id}`, `upvotes` retained in `raw`
- [x] 3.2 RED `test_hf_papers.py::test_parse_below_threshold_dropped` — paper with `upvotes < min_upvotes` absent from result
- [x] 3.3 RED `test_hf_papers.py::test_parse_malformed_returns_empty_no_raise` — `json_malformed.json` bytes -> `[]`, no exception
- [x] 3.4 RED `test_hf_papers.py::test_parse_empty_returns_empty` — empty papers array -> `[]`
- [x] 3.5 GREEN create `collection/hf_papers.py::parse_hf_papers(data, min_upvotes, max_chars)`
- [x] 3.6 RED `test_hf_papers.py::test_collector_fetch_failure_isolated` — injected fetcher raises -> `collect()` returns `[]`, logs
- [x] 3.7 GREEN `HfPapersCollector.__init__(fetcher, summary_max_chars, min_upvotes)` mirroring `RssCollector`'s two-try fetch/parse isolation + `dataclasses.replace` stamping of source/priority/category

## Phase 4: HN collector (`collection/hn_algolia.py`, NEW) — Req: HN Algolia Parsing / Score Threshold / Failure Isolation

- [x] 4.1 RED `test_hn_algolia.py::test_parse_valid_external_url` — non-null `hits[].url` -> `Item.url` equals it
- [x] 4.2 RED `test_hn_algolia.py::test_parse_null_url_falls_back_to_permalink` — null `url` -> `Item.url == https://news.ycombinator.com/item?id={objectID}`, permalink present in `raw`
- [x] 4.3 RED `test_hn_algolia.py::test_parse_below_threshold_dropped` — `points < min_points` absent from result
- [x] 4.4 RED `test_hn_algolia.py::test_parse_malformed_returns_empty_no_raise` — `json_malformed.json` bytes -> `[]`, no exception
- [x] 4.5 RED `test_hn_algolia.py::test_parse_empty_returns_empty` — empty `hits` -> `[]`
- [x] 4.6 GREEN create `collection/hn_algolia.py::parse_hn_algolia(data, min_points, max_chars)`
- [x] 4.7 RED `test_hn_algolia.py::test_collector_fetch_failure_isolated` — injected fetcher raises -> `collect()` returns `[]`, logs
- [x] 4.8 GREEN `HnAlgoliaCollector.__init__(fetcher, summary_max_chars, min_points)`, same isolation pattern

## Phase 5: Source loading (`collection/sources.py`) — Req: Source Loading Includes All Collector Types

- [x] 5.1 RED replace `test_sources.py::test_filters_out_non_rss_collectors` with `test_returns_all_valid_collector_types` — `rss`+`hf_papers`+`hn_algolia` entries all present in the returned list
- [x] 5.2 GREEN `sources.py`: drop the trailing `if source.collector == "rss"` filter; return all valid sources; update docstring/comment; keep the per-entry missing-key skip unchanged

## Phase 6: CLI dispatch (`cli.py`) — Req: Collector Dispatch by Source / Config Wiring

- [x] 6.1 RED update `tests/integration/test_collect_integration.py` — `rss`/`hf_papers`/`hn_algolia` sources each route to their matching collector; a source with an unknown `collector` value is logged, skipped, and the run still exits 0 with items from the rest
- [x] 6.2 GREEN `cli.py::collect()` — build one `HttpxFetcher`, a `{"rss": RssCollector(...), "hf_papers": HfPapersCollector(...), "hn_algolia": HnAlgoliaCollector(...)}` dispatch map wired from `config.hf_min_upvotes`/`config.hn_min_points`; per-source lookup via `.get()`, log + skip on miss instead of crashing

## Phase 7: Dedup interaction (`tests/integration/test_collect_integration.py`) — Req: Dedup Compatibility

- [x] 7.1 RED extend the integration test — an HN item and an RSS item sharing the same canonical URL dedup to exactly one stored item
- [x] 7.2 GREEN confirm pass with no production change (canonical-URL dedup already covers this); adjust only if a real gap surfaces

## Phase 8: `sources.yaml`

- [x] 8.1 Add `Hugging Face Daily Papers` (`collector: hf_papers`, priority 1) and `Hacker News (AI)` (`collector: hn_algolia`, priority 1) entries
- [x] 8.2 Add the 14 P2 `collector: rss` entries from `docs/source-selection.md`: Google Research, Qwen, arXiv cs.AI, arXiv cs.CL, Reddit r/LocalLLaMA, Ahead of AI, Latent Space, The Decoder, Ben's Bites, VentureBeat AI, TechCrunch AI, MIT Technology Review AI, Ollama, Hugging Face Blog

## Phase 9: Docs (`docs/architecture.md`)

- [x] 9.1 Fix the collector table row and the Hugging Face Daily Papers YAML example — replace the `RssCollector`-handles-JSON-APIs claim and the `collector: rss # JSON API handled by the same collector` comment with the accurate dedicated-collector description

## Phase 10: Final Gates

- [x] 10.1 Run full `uv run pytest` — all green (155 passed)
- [x] 10.2 Run `uv run ruff check .` — clean
- [x] 10.3 Cross-check every scenario in `specs/json-collection/spec.md` and the `specs/collect-cli/spec.md` delta has a corresponding passing test
