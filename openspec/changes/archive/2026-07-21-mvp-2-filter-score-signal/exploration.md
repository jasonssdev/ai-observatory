# Exploration: mvp-2-filter-score-signal (deterministic score-keep rule)

> Filesystem mirror of Engram artifact `sdd/mvp-2-filter-score-signal/explore` (id 1475).
> The explore executor had no Write tool; this file restores openspec parity.

## Goal

Close the roadmap gap (`docs/roadmap.md` L42: deterministic layer = "source priority
+ keyword/score thresholds"). Today the filter uses ONLY source-priority auto-keep +
noise-keyword drop. The numeric score (HF upvotes / HN points) is collected and
retained in `Item.raw` but the FILTER ignores it. Add a THIRD deterministic rule:
`score >= per-source KEEP threshold -> SIGNIFICANT` deterministically (skip LLM),
mirroring P1 auto-keep. Thresholds MUST be per-source (HN points and HF upvotes are
different scales). ~1-day enhancement, no redesign.

## Current State

- `synthesis/filter.py::score(item, config)` is a PURE function. Precedence today:
  (1) `source_priority <= filter_keep_priority` -> SIGNIFICANT; (2) noise-keyword
  substring in title+summary -> ROUTINE; (3) `None` (UNCERTAIN -> LLM).
  `classify_items(items, llm_client, config)` calls `score()` first; only UNCERTAIN
  items hit the LLM; the run degrades to deterministic-only on the first `LLMError`.
  `score()` already receives `config` and `item` (incl. `item.raw`), so NO signature
  change is needed.
- Score storage differs by source and nesting level:
  - HF (`collection/hf_papers.py`): `raw = json.dumps(entry)`, score NESTED at
    `entry["paper"]["upvotes"]` (int).
  - HN (`collection/hn_algolia.py`): `raw = json.dumps(hit)`, score TOP-LEVEL at
    `hit["points"]` (int).
  - RSS: no score key at all -> rule must simply not fire.
  Neither payload has a top-level `score`/`signal_score` key, so a namespaced
  normalized key will not collide.
- Collection-time floors (unchanged, out of scope): `AIOBS_HF_MIN_UPVOTES`=5,
  `AIOBS_HN_MIN_POINTS`=30 via `_int_env`.
- `Config` is a frozen dataclass built in `from_env()`; helpers `_int_env`/`_float_env`
  fail-safe to defaults (negative -> default). No optional-int helper exists yet.
- CLI wiring: `cli.py` `classify_items(unclassified, llm_client, config)`; items loaded
  from DB carry `raw`. No CLI change needed.

## Key sub-problem: scale selection

Normalizing the VALUE into one key does NOT remove the need to pick the RIGHT
per-source threshold, because scales differ. `Item` carries only `source` (yaml name,
user-editable = fragile), `source_priority`, `category` — no stable collector-kind
marker. The design must carry a stable per-item scale tag OR detect scale from raw
shape. `Source.collector` ("rss"/"hf_papers"/"hn_algolia") exists at collection time
but is NOT on `Item`.

## Approaches

1. **A — Collectors normalize into `raw` (recommended, LOCKED).** Each JSON collector
   stamps a small envelope into raw: `raw["signal_score"]=<int>` and
   `raw["signal_scale"]="hf_upvotes"|"hn_points"`. Filter parses raw, reads
   `signal_score`, maps `signal_scale` -> the matching config keep threshold. RSS has
   neither key -> rule never fires. Pros: keeps `score()` source-agnostic against a
   STABLE cross-layer contract; robust scale selection; clean hexagonal layering.
   Cons: touches 2 collectors + their tests; adds a json-collection delta; slightly
   bends the `Item.raw` docstring (mitigated: additive namespaced keys). Effort:
   Low-Medium.
2. **B — Filter reads native raw keys directly.** `score()` inspects top-level
   `points` -> HN, nested `paper.upvotes` -> HF. Pros: smallest blast radius. Cons:
   LAYERING VIOLATION — synthesis hard-codes collection payload shapes; brittle.
   Effort: Low. (Fallback only.)
3. **C — Add typed `Item.score: int|None` field + column.** Rejected: schema migration,
   touches all collectors + serialization + tests; `Item.score` column was an EXPLICIT
   json-collection non-goal. Effort: High.

## Recommendation

**Approach A** — preserves the pure, source-agnostic `score()` and clean layering, and
solves scale selection robustly via a stable collector-set tag rather than fragile yaml
names. Namespaced keys (`signal_score`, `signal_scale`) avoid collisions.

## Rule precedence (LOCKED)

1. P1 source-priority auto-keep -> SIGNIFICANT
2. **Score-keep (score >= per-source keep threshold) -> SIGNIFICANT [NEW]**
3. Noise-keyword drop -> ROUTINE
4. `None` (UNCERTAIN -> LLM)

P1 and high-score are both POSITIVE significance signals in the same auto-keep tier;
the noise-keyword drop is a weaker negative heuristic. Score-keep BEFORE the keyword
drop means a very-high-score item OVERRIDES a noise-keyword match (high score = strong
signal). Keep thresholds are set high (well above 5/30 floors), so only genuinely viral
items auto-keep.

## Config design (LOCKED)

- New fields: `filter_hf_keep_upvotes: int | None`, `filter_hn_keep_points: int | None`
  (env `AIOBS_FILTER_HF_KEEP_UPVOTES`, `AIOBS_FILTER_HN_KEEP_POINTS`).
- Add `_optional_int_env(name) -> int | None`: returns `None` when unset/invalid/negative;
  a positive int otherwise. **None = rule DISABLED** for that source.
- **Opt-in (default None).** Zero behavior change until an operator opts in; good
  thresholds are tuning-specific; `0` cannot mean "disable" (score>=0 is always true).
  Documented starter values (NOT enforced defaults): HF ~50 upvotes, HN ~200 points.

## Mandatory new tests

`tests/unit/test_filter.py`: score>=keep -> SIGNIFICANT via `score()`; via
`classify_items` the LLM is NOT called; below-keep -> falls through; boundary (>=);
RSS no-score -> no fire; per-source independence; missing/None threshold -> disabled;
precedence (noise-keyword + high score -> SIGNIFICANT); defensive malformed/empty raw
-> no exception; update `_config` helper with the two new fields (default None).
Collector tests: assert `signal_score`/`signal_scale` present in `raw` for HF and HN.
Config tests: default None when unset; parse when set; invalid/negative -> None.

## Spec deltas

- `hybrid-filter` (MODIFIED, always): ADD "Deterministic Auto-Keep for High-Score
  Items" requirement + scenarios; extend "Configuration-Driven Thresholds" to cover
  `AIOBS_FILTER_HF_KEEP_UPVOTES`/`AIOBS_FILTER_HN_KEEP_POINTS` incl. None=disabled.
- `json-collection` (MODIFIED, Approach A only): ADD requirement that HF/HN collectors
  retain a NORMALIZED significance score (+ scale tag) in `raw`. Still consistent with
  the existing `Item.score` column non-goal — a raw key, not a column.

## Non-goals (confirmed)

No change to the LLM classification path or prompt; no change to collection-time floors;
no `Item.score` column; no weekly briefing; no scheduling; no new sources.

## Risks

- Ordering decision (score-keep vs noise-keyword) is a product/tuning judgment.
- Opt-in vs on-by-default is a UX decision affecting whether the gap is closed
  out-of-the-box; opt-in + docs chosen.
- Approach A slightly bends the `Item.raw` docstring; keep keys namespaced + additive.
- Defensive raw parsing is mandatory (malformed JSON must not raise in pure `score()`).
