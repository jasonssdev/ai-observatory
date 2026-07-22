# Delta for hybrid-filter

## MODIFIED Requirements

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
(Previously: matched by plain substring, which misread "not significant"
and "insignificant" as `SIGNIFICANT` because they contain the substring
"significant".)

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
(Previously: the prompt asked for a one-word verdict with no rubric
guidance on what counts as significant vs. routine.)

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
