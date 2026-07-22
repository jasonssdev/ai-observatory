# Delta for hybrid-filter

## ADDED Requirements

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

## MODIFIED Requirements

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
(Previously: covered only priority threshold and score-keep thresholds;
now extended with the routine-category set field.)

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
