# hybrid-filter Specification

## Purpose

Curate collected items into significant vs routine before rendering: cheap
deterministic rules auto-decide the obvious cases; the local LLM
(`LLMClient` port) classifies only the uncertain remainder. The run MUST
never fail because the LLM is unavailable.

## Non-Goals

- Source expansion, `synthesize --daily` CLI, weekly briefing, scheduling.
- LLM `format:"json"` / batch classification, retry/backoff.

## Requirements

### Requirement: Deterministic Auto-Keep for High-Priority Sources
An item whose `source_priority` equals `1` MUST be classified `SIGNIFICANT`
by rule, without invoking the `LLMClient`.

#### Scenario: P1 item is auto-kept
- GIVEN an item with `source_priority == 1`
- WHEN it is classified
- THEN it is marked `SIGNIFICANT` and the `LLMClient` is never called

### Requirement: Deterministic Auto-Keep for High-Score Items
An item whose `raw` carries a `signal_score` at or above the matching
per-source keep threshold (selected via `raw["signal_scale"]`) MUST be
classified `SIGNIFICANT` by rule, without invoking the `LLMClient`. This
rule MUST be evaluated before the noise-keyword rule. Reading `signal_score`
MUST NOT raise; missing, non-int, or unrecognized `signal_scale` simply
means the rule does not fire.

#### Scenario: High score is auto-kept
- GIVEN an item with `raw["signal_score"] >=` its source's keep threshold
- WHEN it is classified
- THEN it is marked `SIGNIFICANT` and the `LLMClient` is never called

#### Scenario: High score overrides a noise keyword
- GIVEN an item whose score meets its keep threshold AND whose title or
  summary matches a configured noise keyword
- WHEN it is classified
- THEN it is marked `SIGNIFICANT` (score-keep takes precedence over the
  noise-keyword rule)

#### Scenario: Below-threshold score falls through
- GIVEN an item with `raw["signal_score"]` below its source's keep threshold
- WHEN it is classified
- THEN score-keep does not fire and classification proceeds via the
  noise-keyword/LLM path unchanged

#### Scenario: Disabled threshold never fires
- GIVEN the matching per-source keep threshold is `None` (default)
- WHEN an item with a `signal_score` is classified
- THEN score-keep does not fire, regardless of the score's value

#### Scenario: RSS item is unaffected
- GIVEN an item whose `raw` has no `signal_score`/`signal_scale`
- WHEN it is classified
- THEN score-keep does not fire

#### Scenario: Per-source threshold independence
- GIVEN an HF item and an HN item, each with a `signal_score` at or above
  only its own source's configured keep threshold
- WHEN both are classified
- THEN each is compared solely against the threshold matching its
  `signal_scale`, independent of the other source's threshold

#### Scenario: Malformed score never raises
- GIVEN an item whose `raw` has a missing, non-int `signal_score`, or an
  unrecognized `signal_scale`
- WHEN it is classified
- THEN no exception is raised and score-keep does not fire

### Requirement: Deterministic Routine for Research Categories
An item whose normalized `category` is a member of the configured
`filter_routine_categories` set MUST be classified `ROUTINE` by rule,
without invoking the `LLMClient`. This rule MUST run after the P1 auto-keep
rule and the score-keep rule, and before the noise-keyword rule. Reading
`category` MUST NOT raise; a missing/empty/unrecognized `category`, or an
empty `filter_routine_categories` set, means the rule simply does not fire.

#### Scenario: Research-category item routes to ROUTINE, no LLM call
- GIVEN a non-P1 item with `category == "research"` and the default set
- WHEN it is classified via `classify_items`
- THEN it is `ROUTINE` and `LLMClient` is never called

#### Scenario: P1 research item still wins auto-keep
- GIVEN an item with `source_priority == 1` and `category == "research"`
- WHEN it is classified
- THEN it is `SIGNIFICANT` via P1 auto-keep; the routine rule never fires

#### Scenario: High-score research item still wins score-keep
- GIVEN a non-P1 `category == "research"` item at/above its keep threshold
- WHEN it is classified
- THEN it is `SIGNIFICANT` via score-keep; the routine rule never fires

#### Scenario: Non-routine category flows unchanged
- GIVEN an item whose `category` is not in the routine set (e.g. `"news"`)
- WHEN it is classified
- THEN the routine rule does not fire; noise-keyword/LLM path is unchanged

#### Scenario: Disabled routine-category set never fires
- GIVEN `filter_routine_categories` resolves to an empty set
- WHEN a `category == "research"` item is classified
- THEN the routine rule does not fire, regardless of category

#### Scenario: Raised auto-keep priority still precedes the routine rule
- GIVEN `filter_keep_priority` raised to include P2, item has
  `source_priority == 2` and `category == "research"`
- WHEN it is classified
- THEN it is `SIGNIFICANT` via priority auto-keep before the routine rule
  runs

#### Scenario: Malformed category never raises
- GIVEN an item whose `category` is missing, empty, or unrecognized
- WHEN it is classified
- THEN no exception is raised and the routine rule does not fire

#### Scenario: Daily record reflects the routine verdict
- GIVEN a research-category item classified `ROUTINE` by this rule
- WHEN daily records are rendered
- THEN it appears in the set-aside/routine section, not Significant

### Requirement: Deterministic Drop for Noise Keywords
An item whose title or summary matches a configured noise keyword MUST be
classified `ROUTINE` by rule, without invoking the `LLMClient`.

#### Scenario: Noise-keyword item is set aside
- GIVEN a non-P1 item whose title matches a configured noise keyword
- WHEN it is classified
- THEN it is marked `ROUTINE` and the `LLMClient` is never called

### Requirement: LLM Verdict for Uncertain Items
An item that is neither auto-kept nor auto-dropped (UNCERTAIN) MUST be sent
to the injected `LLMClient` for a one-word verdict (`SIGNIFICANT` or
`ROUTINE`), and the returned verdict MUST determine its classification. The
classification prompt MUST include a significance rubric distinguishing
`SIGNIFICANT` (a notable development: a major model or product release, a
research breakthrough, or an important policy/safety/funding item with
real-world impact) from `ROUTINE` (incremental updates, tutorials,
opinion/commentary, roundups/newsletters, and minor releases), and MUST
instruct the model to answer with a single word. The rubric wording is an
operator-tunable starting point, not a fixed contract.

#### Scenario: LLM verdict significant keeps the item
- GIVEN an UNCERTAIN item and an injected `LLMClient` that returns
  `SIGNIFICANT`
- WHEN it is classified
- THEN it is marked `SIGNIFICANT`

#### Scenario: LLM verdict routine sets the item aside
- GIVEN an UNCERTAIN item and an injected `LLMClient` that returns `ROUTINE`
- WHEN it is classified
- THEN it is marked `ROUTINE`

#### Scenario: Prompt carries the significance rubric and item content
- GIVEN an UNCERTAIN item with a title and summary
- WHEN the classification prompt is built for that item
- THEN the prompt text includes the SIGNIFICANT/ROUTINE rubric wording, an
  instruction to answer with a single word, and the item's title and
  summary

### Requirement: Tolerant Parsing with Safe Default
The LLM verdict parser MUST normalize case/whitespace and determine the
verdict from the leading verdict word using word-boundary matching (not
substring matching), and MUST be negation-aware: a leading negation of
"significant" (e.g. "not significant") or the word "insignificant" MUST
resolve to `ROUTINE`, never `SIGNIFICANT`. A response beginning with the
word "SIGNIFICANT" (optionally followed by other text) MUST resolve to
`SIGNIFICANT`. When the response is unparseable, empty, or ambiguous (no
verdict word identifiable via this word-boundary/negation logic), the
parser MUST default to `ROUTINE`.

#### Scenario: Malformed LLM output defaults to routine
- GIVEN an UNCERTAIN item and an injected `LLMClient` that returns an
  unparseable or ambiguous string
- WHEN it is classified
- THEN it is marked `ROUTINE` as the documented safe default

#### Scenario: Exact significant verdict is parsed
- GIVEN an LLM response of `"SIGNIFICANT"`
- WHEN the verdict is parsed
- THEN it resolves to `SIGNIFICANT`

#### Scenario: Exact routine verdict is parsed
- GIVEN an LLM response of `"ROUTINE"`
- WHEN the verdict is parsed
- THEN it resolves to `ROUTINE`

#### Scenario: Negated significance is not misread as significant
- GIVEN an LLM response of `"This is not significant, it's routine."`
- WHEN the verdict is parsed
- THEN it resolves to `ROUTINE`

#### Scenario: The word "insignificant" is not misread as significant
- GIVEN an LLM response of `"insignificant"`
- WHEN the verdict is parsed
- THEN it resolves to `ROUTINE`

#### Scenario: Leading verdict with trailing commentary is parsed
- GIVEN an LLM response of `"SIGNIFICANT — major model release"`
- WHEN the verdict is parsed
- THEN it resolves to `SIGNIFICANT`

#### Scenario: Empty response defaults to routine
- GIVEN an LLM response that is empty or whitespace-only
- WHEN the verdict is parsed
- THEN it resolves to `ROUTINE`

#### Scenario: Case and whitespace variations normalize correctly
- GIVEN an LLM response such as `"  significant\n"` or `"Significant."`
- WHEN the verdict is parsed
- THEN it resolves to `SIGNIFICANT`

### Requirement: Run-Level Fallback on LLM Unavailability
On the first `LLMError` raised by the `LLMClient` during a run, the ENTIRE
run MUST degrade to deterministic-only classification: the run MUST NOT
fail or abort, and all remaining UNCERTAIN items in that run MUST be
classified by rule (never `SIGNIFICANT` by default) instead of being sent
to the LLM.

#### Scenario: LLM unavailable degrades the whole run
- GIVEN multiple UNCERTAIN items and an injected `LLMClient` whose first
  call raises an `LLMError`
- WHEN the run classifies all items
- THEN the run completes without error, the failing item and all
  subsequent UNCERTAIN items are classified deterministically, and no
  further `LLMClient` calls are attempted

### Requirement: Idempotent Classification
An item that already has a persisted significance verdict MUST NOT be
re-classified (deterministically or via LLM) on a subsequent `collect` run.

#### Scenario: Already-classified item is skipped on re-run
- GIVEN an item with an existing significance verdict from a prior run
- WHEN `collect` runs again
- THEN the item is not reclassified and its stored verdict is unchanged

### Requirement: Configuration-Driven Thresholds
Deterministic classification MUST be governed by `AIOBS_FILTER_*` settings
(auto-keep priority threshold, per-source score-keep thresholds,
routine-category set), each with a documented default when unset, missing,
or invalid. Score-keep thresholds (`filter_hf_keep_upvotes` from
`AIOBS_FILTER_HF_KEEP_UPVOTES`, `filter_hn_keep_points` from
`AIOBS_FILTER_HN_KEEP_POINTS`) are `int | None`, defaulting to `None`
(disabled) when unset, non-integer, or negative. The routine-category set
(`filter_routine_categories` from `AIOBS_FILTER_ROUTINE_CATEGORIES`,
comma-separated) is a `frozenset[str]`, normalized lowercase/trimmed,
defaulting to `{"research"}` when unset; an explicit blank value resolves
to an empty set (disabled).

#### Scenario: Defaults apply when unset
- GIVEN no `AIOBS_FILTER_*` environment variables are set
- WHEN configuration is resolved
- THEN each setting equals its default: score-keep thresholds `None`,
  routine-category set `{"research"}`

#### Scenario: Overrides apply when set
- GIVEN valid `AIOBS_FILTER_*` overrides, including
  `AIOBS_FILTER_HF_KEEP_UPVOTES`/`AIOBS_FILTER_HN_KEEP_POINTS`
- WHEN configuration is resolved
- THEN each setting equals its environment value, including parsed
  score-keep thresholds

#### Scenario: Invalid score-keep override falls back to disabled
- GIVEN a score-keep var set to a non-integer or negative value
- WHEN configuration is resolved
- THEN it falls back to `None` (disabled); resolution does not raise

#### Scenario: Routine-category override is parsed and normalized
- GIVEN `AIOBS_FILTER_ROUTINE_CATEGORIES` set with mixed case/whitespace
  (e.g. `" Research, Lab "`)
- WHEN configuration is resolved
- THEN `filter_routine_categories` equals `{"research", "lab"}`

#### Scenario: Blank routine-category value disables the rule
- GIVEN `AIOBS_FILTER_ROUTINE_CATEGORIES` set to an empty/blank string
- WHEN configuration is resolved
- THEN `filter_routine_categories` equals the empty frozenset

### Requirement: Classification Scope Matches the Render Window
During a `collect` run, classification MUST cover every unclassified item
whose `published_at` falls within the render window — the same window
`_write_daily_records` renders, bounded by `record_window_days` (mirroring
`records.dates_within_window`) — not only items published on the current
UTC run-day. Items already carrying a persisted verdict remain excluded per
Idempotent Classification (unchanged). Run-Level Fallback on LLM
Unavailability (unchanged) continues to govern degraded runs across this
wider scope.

#### Scenario: In-window item published on a prior day is classified
- GIVEN an unclassified item with `published_at` on a day before today but
  within the render window
- WHEN `collect` runs
- THEN the item is classified and receives a persisted significance verdict

#### Scenario: Out-of-window item is not classified
- GIVEN an unclassified item with `published_at` older than the render
  window
- WHEN `collect` runs
- THEN the item is not classified and receives no verdict

#### Scenario: Idempotency holds across the wider scope
- GIVEN an item within the render window that already has a persisted
  verdict
- WHEN `collect` runs again
- THEN the item is not reclassified and its stored verdict is unchanged

#### Scenario: Run-level LLM fallback holds across the wider scope
- GIVEN multiple UNCERTAIN items spread across several days within the
  render window, and an injected `LLMClient` whose first call raises an
  `LLMError`
- WHEN `collect` classifies the window-scoped unclassified set
- THEN the run completes without error and every remaining UNCERTAIN item
  in the window, regardless of its published date, is classified
  deterministically
