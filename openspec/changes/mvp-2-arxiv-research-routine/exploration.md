# Exploration: MVP-2 route research/arXiv (P2) items to ROUTINE deterministically

> Filesystem mirror of Engram artifact `sdd/mvp-2-arxiv-research-routine/explore` (id 1559).
> The explore executor had no Write tool; this file restores openspec parity.

## Problem

Live run 2026-07-22 (`mistral:7b`): the LLM marked 33 individual arXiv papers
SIGNIFICANT (~42% of its 79 SIGNIFICANT verdicts), burying real P1 lab news. All 33
confirmed `item_significance.mode='LLM'`. arXiv feeds are P2, so the P1 auto-keep rule
(`keep_priority=1`) does not touch them and they flow to the LLM.

## Current State (filter pipeline, `synthesis/filter.py::score()`)

Deterministic precedence today:
1. `source_priority <= filter_keep_priority` (P1) -> SIGNIFICANT
2. score-keep: `raw[signal_score] >= scale threshold` (hf_upvotes/hn_points) -> SIGNIFICANT
3. noise keyword in title/summary -> ROUTINE
4. else -> None (UNCERTAIN) -> LLM `build_prompt` -> `parse_verdict`

`classify_items` (called from `cli.py:141`) runs deterministic-first, LLM for the rest,
degrades to deterministic-only on first `LLMError`.

Crucial: the prompt was ALREADY hardened by the archived `mvp-2-filter-signal-quality`
change. `build_prompt` already contains the rubric line "ROUTINE = individual academic
or arXiv papers" AND the anti-example "'A new arXiv paper proposes a benchmark for tool
use' -> ROUTINE". Despite this, `mistral:7b` still misclassified 33 papers. This is
direct evidence that prompt-only hardening is unreliable on a 7B model.

## Data model / discriminator (key finding)

`Item` (`storage/models.py`) carries `source`, `source_priority: int`, and
`category: str`. `category` originates from `sources.yaml` (required key, loaded by
`collection/sources.py`) with the fixed vocabulary: lab, research, newsletter, news,
tooling, community. It flows `Source.category -> Item.category` at collection and is a
persisted column.

Research-tagged sources in `sources.yaml` today:
- Hugging Face Daily Papers — category: research, priority: 1 (already auto-kept by rule #1; unaffected)
- Google Research — category: research, priority: 2
- arXiv cs.AI — category: research, priority: 2
- arXiv cs.CL — category: research, priority: 2

So `category == "research"` cleanly identifies research/arXiv WITHOUT brittle string
matching. Combined with the existing rule ordering, a research-routine rule placed AFTER
the two auto-keep rules only ever reaches non-auto-kept (P2+) research items — exactly
the target set. No `sources.yaml` change needed (categories already correct).

## Affected Areas

- `src/ai_observatory/synthesis/filter.py` — add a deterministic research-routine rule in `score()`; mirror score-keep shape.
- `src/ai_observatory/config.py` — add config surface (`AIOBS_FILTER_ROUTINE_CATEGORIES`) + parser helper; wire field into frozen `Config`.
- `tests/unit/test_filter.py` — TDD: research-category -> ROUTINE; auto-keep precedence; non-research unaffected; disabled/empty config no-fire; `classify_items` short-circuits LLM (`client.calls==0`).
- `tests/unit/test_config.py` — parser helper (unset/blank/invalid -> disabled; valid -> parsed set).
- `openspec/specs/hybrid-filter/spec.md` — add "Deterministic Routine for Research Categories" requirement + scenarios; extend Configuration-Driven Thresholds.
- Optional complement: `build_prompt` (already has arXiv anti-example).

## Approaches

1. **Deterministic category-routine rule (PREFERRED)** — In `score()`, after the two
   SIGNIFICANT auto-keep rules and before/alongside the noise-keyword rule, route items
   whose `category` is in a configured routine-category set to ROUTINE. Config-driven via
   a new `AIOBS_FILTER_ROUTINE_CATEGORIES` (comma-separated -> frozenset[str]), mirroring
   the score-keep opt-in precedent. Uses the already-modeled `category` field — no string
   parsing, no schema change, no `sources.yaml` change.
   - Pros: reliable/deterministic (not model-dependent); reuses proven score-keep
     config+rule shape; targets exactly P2 research via existing rule ordering; removes
     ~33 LLM calls/run; pure, no I/O, no signature change; trivially testable.
   - Cons: coarser than per-source — also routes Google Research (P2, research) to
     ROUTINE; `category` is free-text from YAML so a typo/new value silently won't match;
     introduces a default-on-vs-off policy decision.
   - Effort: Low.
2. **Prompt hardening (COMPLEMENT ONLY)** — Add more arXiv anti-examples. ALREADY
   ATTEMPTED and demonstrably insufficient on 7B; every research paper still costs an LLM
   call; non-deterministic. Cannot meet the "trust without cross-checking" bar.
3. **Config source-name allowlist (alternative discriminator)** —
   `AIOBS_FILTER_ROUTINE_SOURCES="arXiv cs.AI,arXiv cs.CL"`. Surgically precise but
   brittle string matching against display names; ongoing maintenance. Effort: Low-Med.

## Recommendation

Approach 1 (deterministic category-routine rule), config-driven, reusing the score-keep
pattern. Only approach that reliably meets the MVP-2 "Done when" bar given a 7B local
model. Prefer `category`-based discrimination over a source allowlist for cleanliness;
if suppressing Google Research proves undesirable in real-run tuning, the config set can
be narrowed or switched to a source allowlist later.

## Key design decisions to resolve in propose/design

- Precedence: place research-routine AFTER both SIGNIFICANT auto-keep rules and BEFORE
  the LLM. Relative order vs noise-keyword is immaterial (both -> ROUTINE); simplest is
  right after score-keep.
- Default policy fork: default the routine-category set to EMPTY (opt-in, matches
  score-keep precedent) vs default to `{"research"}` (fixes the reported bug
  out-of-the-box, aligns with roadmap intent). Genuine tradeoff for propose to decide.
- Config type: comma-separated string -> normalized (lowercased, trimmed) frozenset;
  blank/unset -> empty set (disabled), never raises.

## Risks

- Over-suppression: Google Research (P2 research) routed to ROUTINE may hide an occasional
  notable post; mitigate via config and real-run tuning.
- Category is free-text from `sources.yaml`; misspelled/renamed categories silently won't
  match. Low likelihood (fixed vocabulary, loader requires the key).
- Default-on changes current behavior (intended); default-off requires the operator to
  set the env var to get the fix.
- Interaction with a raised `filter_keep_priority` (e.g. =2): P2 would be auto-kept
  SIGNIFICANT before the research rule — correct by ordering, but worth an explicit test.

## Scope boundaries / Non-goals

- Do NOT touch collection, dedup, storage schema, or MVP-3 synthesis.
- No `sources.yaml` change required (categories already correct).
- No `Item`/DB schema change; no new modules; no `classify_items`/`score()` signature change.
- Ollama structured-output/`format:json` adapter remains out of scope.
