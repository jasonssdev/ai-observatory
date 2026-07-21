# Verify Report: mvp-2-source-expansion

**Mode**: hybrid (Engram + openspec file)
**Verdict**: PASS WITH WARNINGS
**Tasks**: 34/34 checked in tasks.md, all confirmed implemented in code.

## Test / Lint Evidence

- `uv run pytest -q` → **155 passed**, 0 failed, 0 skipped (matches apply-progress claim exactly).
- `uv run ruff check .` → **All checks passed**.
- No residual `collector == "rss"` filter anywhere in `src/` (grep-confirmed).

## Scenario → Test Matrix (json-collection)

| Requirement / Scenario | Covering test | Result |
|---|---|---|
| Valid HF payload normalizes | `test_hf_papers.py::TestParseHfPapers::test_parse_valid_maps_fields` | PASS |
| Malformed HF JSON yields no items | `...::test_parse_malformed_returns_empty_no_raise` | PASS |
| Empty HF payload yields no items | `...::test_parse_empty_returns_empty` | PASS |
| HF paper below threshold dropped | `...::test_parse_below_threshold_dropped` | PASS |
| Valid HN payload, external URL | `test_hn_algolia.py::TestParseHnAlgolia::test_parse_valid_external_url` | PASS |
| Null URL falls back to permalink | `...::test_parse_null_url_falls_back_to_permalink` | PASS |
| Malformed HN JSON yields no items | `...::test_parse_malformed_returns_empty_no_raise` | PASS |
| Empty HN payload yields no items | `...::test_parse_empty_returns_empty` | PASS |
| HN story below threshold dropped | `...::test_parse_below_threshold_dropped` | PASS |
| Defaults apply when unset (HF/HN) | `test_config.py::TestHfMinUpvotes/TestHnMinPoints::test_unset_defaults_to_*` | PASS |
| Invalid override falls back to default | `...::test_non_integer_value_falls_back_to_*`, `test_negative_value_falls_back_to_*` (both HF/HN) | PASS |
| Fetch failure isolated (HF/HN) | `TestHfPapersCollectorIsolation`/`TestHnAlgoliaCollectorIsolation::test_collector_fetch_failure_isolated` | PASS |
| Unreachable JSON source among many | Proven indirectly: unit-level collector isolation (above) + `TestCollectorDispatch` loop structure (no try/except around `collector.collect()` in `cli.py`, relying on collector self-isolation) | PASS (indirect) — see SUGGESTION below |
| JSON item dedups against RSS by canonical URL | `test_collect_integration.py::TestJsonRssDedupCompatibility::test_hn_item_and_rss_item_sharing_canonical_url_dedup_to_one` | PASS |
| HF item dedups against equivalent-title RSS item | `...::test_hf_item_dedups_against_equivalent_title_rss_item` (added beyond literal task list, closes explicit spec gap) | PASS |

## Scenario → Test Matrix (collect-cli delta)

| Requirement / Scenario | Covering test | Result |
|---|---|---|
| Each source routes to matching collector | `TestCollectorDispatch::test_each_source_routes_to_its_matching_collector` | PASS |
| Unknown collector skipped, not fatal | same test (asserts unsupported source absent, run completes exit 0) | PASS |
| P2 RSS feeds use existing RssCollector | Implicit — P2 entries use `collector: rss`, exercised by pre-existing RSS test suite; no distinct new test needed | PASS |
| Config defaults (incl. HF/HN thresholds) | `TestConfigDefaultsAndOverrides` + `TestHfMinUpvotes`/`TestHnMinPoints` | PASS |
| Env override takes effect | `TestConfigDefaultsAndOverrides` (pre-existing, unaffected) | PASS |
| Invalid/negative window & summary cap fallback | `TestRecordWindowDays`, `TestSummaryMaxChars` (pre-existing) | PASS |
| Invalid/negative JSON thresholds fallback | `TestHfMinUpvotes`/`TestHnMinPoints::test_negative_value_falls_back_to_*` | PASS |
| `load_sources` returns all valid types | `test_sources.py::TestLoadSources::test_returns_all_valid_collector_types` | PASS |
| Malformed entry still skipped | `...::test_malformed_entry_is_logged_and_skipped_valid_entries_still_load` (pre-existing) | PASS |

## Code-Level Verification (not just tests)

1. **Never-raise contract** — Confirmed by direct inspection of `hf_papers.py` / `hn_algolia.py`: `parse_hf_papers`/`parse_hn_algolia` catch `JSONDecodeError`/`UnicodeDecodeError`, guard every subsequent field access with `isinstance` checks (no unguarded `dict`/`str` access), and the collector wraps fetch and parse in two separate `try/except Exception` blocks, mirroring `rss.py`. No raise path found.
2. **HN canonical URL** — `url = external_url if isinstance(external_url, str) and external_url else _PERMALINK_TEMPLATE.format(...)`; permalink template always uses `objectID`; raw always retains the full original hit (including `objectID`). Verified in code and test.
3. **HF canonical URL + nested upvotes** — `_CANONICAL_URL_TEMPLATE = "https://huggingface.co/papers/{paper_id}"`; `upvotes = paper.get("upvotes")` read from nested `paper` object; `raw = json.dumps(entry, ...)` retains upvotes. Verified in code and test.
4. **Thresholds** — `config.py`: `_DEFAULT_HF_MIN_UPVOTES = 5`, `_DEFAULT_HN_MIN_POINTS = 30`, read via `_int_env("AIOBS_HF_MIN_UPVOTES", 5)` / `_int_env("AIOBS_HN_MIN_POINTS", 30)` (fail-safe to default on missing/non-integer/negative — shared `_int_env` helper). Injected into `HfPapersCollector.__init__`/`HnAlgoliaCollector.__init__` via constructor, then into `parse_*` by the collector. Verified.
5. **`load_sources`** — No `== "rss"` filter remains (grep-confirmed repo-wide); returns all valid entries, keeps per-entry missing-key skip. `sources.yaml` is valid YAML; all 25 entries have `name`/`collector`/`url`/`category`/`priority`.
6. **`sources.yaml`** — HF (`hf_papers`, P1) and HN (`hn_algolia`, P1) present with sensible category/priority. 14 P2 `collector: rss` entries added (Google Research, Qwen, arXiv cs.AI/cs.CL, Reddit r/LocalLLaMA, Ahead of AI, Latent Space, The Decoder, Ben's Bites, VentureBeat AI, TechCrunch AI, MIT Tech Review AI, Ollama, HF Blog) — spot-checked URLs are well-formed. Total 25 entries (9 P1 rss + 2 P1 json + 14 P2 rss), matching apply-progress's claim.
7. **Collectors mirror `rss.py`** — Confirmed structurally identical: pure `parse_*` function, thin `Collector` class with two-try fetch/parse isolation, `dataclasses.replace` stamping of `source`/`source_priority`/`category`, reuse of the same `HttpxFetcher` instance from `cli.py`. Tests inject fake fetchers (`RaisingFetcher`, `StaticFetcher`, `_MultiSourceFetcher`, `_StaticFetcher`) — no live network calls found anywhere in the test suite for these collectors.
8. **`docs/architecture.md`** — Collector table now lists `HfPapersCollector`/`HnAlgoliaCollector` as dedicated rows; YAML example uses `collector: hf_papers` with an explanatory comment. The prior "JSON APIs use `collector: rss`" drift is gone.

## Deviation Assessment

- **`test_filter.py::_config()` helper update** (adding `hf_min_upvotes=5, hn_min_points=30`): correct and in-scope. `Config` is a single shared frozen dataclass; adding two new required fields mechanically breaks any direct `Config(...)` constructor call elsewhere in the suite. This is a necessary consequence of the shared-dataclass change, not scope creep.
- **Added `test_hf_item_dedups_against_equivalent_title_rss_item`**: in-scope. It closes an explicit spec scenario ("HF item dedups against an equivalent-title RSS item") that Phase 7's task list only worded for the HN-vs-RSS canonical-URL case. No production code changed as a result — the pre-existing `dedup_batch`/`_wins` logic already handled it; the test closes a coverage gap the spec explicitly calls for.

## Issues

### CRITICAL
None.

### WARNING
1. **Review workload footprint exceeds even the overridden budget.** Recomputed independently: tracked `git diff --stat` = 393 changed lines (372 insertions + 21 deletions across 9 files) + untracked new code files (hf_papers.py 139, hn_algolia.py 148, test_hf_papers.py 97, test_hn_algolia.py 114 = 498) + fixtures (48) = **~891 authored lines excluding fixtures, ~939 including them** — above both the shared 400-line default guard and the orchestrator's own stated 800-line single-PR override. This is a process/governance concern for the reviewer, not a code defect; tasks.md's original forecast (a 2-PR feature-branch chain) was explicitly superseded by orchestrator instruction, so this is a known, directed tradeoff — but it should be surfaced explicitly before merge, not silently absorbed.

### SUGGESTION
1. **No dedicated integration-level test for "one JSON source unreachable while other sources (RSS + JSON) stay healthy in the same `collect()` run."** The contract is proven correctly at the unit level (both `HfPapersCollector`/`HnAlgoliaCollector.collect()` return `[]` on a raising fetcher, never propagating) and the `cli.py` loop has no defensive `try/except` around `collector.collect(source)` — it structurally depends on each collector's own never-raise contract, which is unit-tested for both HF and HN. An integration test mixing one raising JSON fetcher with healthy RSS/JSON sources in a single `collect()` call would make this end-to-end guarantee explicit rather than inferred from code inspection, but is not required for correctness given the existing coverage.

## Verdict

**PASS WITH WARNINGS** — all spec requirements/scenarios have passing covering tests (one scenario covered indirectly rather than by a dedicated integration test — SUGGESTION only), all 34 tasks are complete and match the implementation, the never-raise contract holds under direct code inspection for both new collectors, `uv run pytest` (155/155) and `uv run ruff check .` are clean, and both flagged apply-progress deviations are correct and in-scope. The only WARNING is a review-workload/process concern (single-PR footprint ~891-939 lines vs. the 800-line override), not a functional defect.
