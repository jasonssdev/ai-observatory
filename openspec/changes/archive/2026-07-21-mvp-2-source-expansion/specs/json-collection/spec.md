# json-collection Specification

## Purpose

Fetch bespoke JSON APIs (HF Daily Papers, HN Algolia) and normalize their
firehose into `Item`s, thresholding by source-native score (`upvotes`,
`points`) before storage, isolating per-source failures exactly like
`RssCollector`.

## Non-Goals

Bridged/RSSHub, Apify/X sources; a generic config-driven `JsonCollector`;
`Item.score` storage column; server-side threshold optimization; hybrid-filter
changes.

## Requirements

### Requirement: HF Daily Papers Parsing
The system MUST parse HF Daily Papers JSON bytes into normalized `Item`s:
`title`, canonical `url = https://huggingface.co/papers/{paper.id}`,
`summary`, `category`, `source`, `source_priority`, and `published_at`.
`paper.upvotes` MUST be retained in `raw`.

#### Scenario: Valid HF payload normalizes
- GIVEN well-formed HF Daily Papers JSON with nested `paper.upvotes`
- WHEN parsed
- THEN one `Item` is returned per paper with `url` equal to
  `https://huggingface.co/papers/{paper.id}` and `raw` containing the
  original `upvotes` value

#### Scenario: Malformed HF JSON yields no items
- GIVEN unparseable or unexpected-shape HF JSON bytes
- WHEN parsed
- THEN zero items are returned, no exception propagates, and the failure is
  logged

#### Scenario: Empty HF payload yields no items
- GIVEN an empty HF papers array
- WHEN parsed
- THEN zero items are returned without error

### Requirement: HN Algolia Parsing
The system MUST parse HN Algolia JSON bytes into normalized `Item`s. Each
item's canonical `url` MUST equal the external `hits[].url` when present, and
MUST fall back to the discussion permalink
`https://news.ycombinator.com/item?id={objectID}` when `hits[].url` is null.
The permalink MUST always be retained in `raw`.

#### Scenario: Valid HN payload with external URL
- GIVEN a well-formed HN Algolia hit with a non-null `url`
- WHEN parsed
- THEN the resulting `Item.url` equals the hit's external `url`

#### Scenario: Null external URL falls back to permalink
- GIVEN a well-formed HN Algolia hit whose `url` is null
- WHEN parsed
- THEN the resulting `Item.url` equals
  `https://news.ycombinator.com/item?id={objectID}` and the permalink is
  present in `raw`

#### Scenario: Malformed HN JSON yields no items
- GIVEN unparseable or unexpected-shape HN JSON bytes
- WHEN parsed
- THEN zero items are returned, no exception propagates, and the failure is
  logged

#### Scenario: Empty HN payload yields no items
- GIVEN an empty `hits` array
- WHEN parsed
- THEN zero items are returned without error

### Requirement: Score Threshold Before Storage
Each JSON collector MUST drop items below a configured cutoff before
returning them, so below-cutoff items never reach dedup or storage. HF drops
papers where `upvotes` is below `AIOBS_HF_MIN_UPVOTES`. HN drops stories
where `points` is below `AIOBS_HN_MIN_POINTS`. The dropped score value MUST
still be derivable from source data (retained in `raw` for surviving items;
dropped items are discarded entirely).

#### Scenario: HF paper below threshold is dropped
- GIVEN an HF paper whose `upvotes` is below `AIOBS_HF_MIN_UPVOTES`
- WHEN the source is collected
- THEN that paper is absent from the returned items

#### Scenario: HN story below threshold is dropped
- GIVEN an HN hit whose `points` is below `AIOBS_HN_MIN_POINTS`
- WHEN the source is collected
- THEN that story is absent from the returned items

### Requirement: Configuration-Driven Thresholds
Threshold cutoffs MUST be read from `AIOBS_HF_MIN_UPVOTES` and
`AIOBS_HN_MIN_POINTS`, each with a documented default (`5` and `30`
respectively) applied when the env var is unset, non-integer, or negative.

#### Scenario: Defaults apply when unset
- GIVEN neither `AIOBS_HF_MIN_UPVOTES` nor `AIOBS_HN_MIN_POINTS` is set
- WHEN a collector runs
- THEN HF uses a minimum of 5 upvotes and HN uses a minimum of 30 points

#### Scenario: Invalid override falls back to default
- GIVEN `AIOBS_HF_MIN_UPVOTES` or `AIOBS_HN_MIN_POINTS` is set to a
  non-integer or negative value
- WHEN a collector runs
- THEN the corresponding threshold falls back to its documented default and
  the run completes without error

### Requirement: Per-Source Failure Isolation
Each JSON collector MUST NOT raise on fetch or parse failure; it MUST log
the failure and return an empty list, matching `RssCollector`'s isolation
contract, so one dead JSON source never aborts collection for the others.

#### Scenario: Unreachable JSON source among many
- GIVEN one JSON source is unreachable while other sources are healthy
- WHEN collection runs
- THEN the healthy sources' items are collected, the run completes, and the
  unreachable source's failure is logged

### Requirement: Dedup Compatibility
JSON-sourced items MUST use the same canonical-URL and title-hash identity
scheme as feed-collection items, so a JSON item and an RSS/Atom item
describing the same story resolve to a single stored item.

#### Scenario: JSON item dedups against an RSS item by canonical URL
- GIVEN an HN item whose canonical URL equals an RSS item's canonical URL
- WHEN both are deduped in the same run
- THEN only one item is kept, identified by the shared canonical URL

#### Scenario: HF item dedups against an equivalent-title RSS item
- GIVEN an HF paper item and an RSS item with the same normalized title but
  different canonical URLs
- WHEN both are deduped in the same run
- THEN the title-hash collision resolution keeps exactly one item per the
  existing priority/publish-time/id tie-break rules
