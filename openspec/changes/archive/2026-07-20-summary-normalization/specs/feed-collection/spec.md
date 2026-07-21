# Delta for feed-collection

## MODIFIED Requirements

### Requirement: Feed Parsing

The system MUST parse fetched feed bytes into zero or more normalized entries
(title, url, published_at, summary, raw source data). `summary` MUST be short,
clean plain text: HTML tags removed, entities unescaped, only the first
paragraph kept, and truncated to `AIOBS_SUMMARY_MAX_CHARS` characters with an
ellipsis when truncated (the total rendered length, including the ellipsis,
MUST NOT exceed the configured maximum). A summary that is empty or contains
only whitespace after normalization MUST be stored as an empty string. `raw`
MUST continue to store the complete, unmodified original entry data as the
source-of-truth safety net; normalization applies to `summary` only.
(Previously: `summary` was stored verbatim from the feed, with no HTML
stripping, entity unescaping, paragraph extraction, or length cap.)

#### Scenario: Well-formed feed parses

- GIVEN well-formed RSS or Atom bytes
- WHEN parsed
- THEN one entry is returned per feed item with title and url populated

#### Scenario: Malformed feed yields no entries

- GIVEN unparseable or malformed feed bytes
- WHEN parsed
- THEN zero entries are returned, no exception propagates, and the failure is
  logged

#### Scenario: HTML entry normalizes to plain text

- GIVEN a feed entry whose summary contains HTML tags and encoded entities
  (e.g. `&amp;`, `&#39;`)
- WHEN parsed
- THEN the stored summary contains no `<...>` tags and entities are decoded
  to their literal characters

#### Scenario: Trailing metadata block is dropped

- GIVEN a feed entry whose summary has a body paragraph followed by a
  `Tags: .../Via: ...` block in a later paragraph
- WHEN parsed
- THEN the stored summary contains only the first paragraph and the trailing
  block is absent

#### Scenario: Long multi-paragraph body is truncated

- GIVEN a feed entry with a multi-paragraph body longer than
  `AIOBS_SUMMARY_MAX_CHARS`
- WHEN parsed
- THEN the stored summary is a single paragraph, its total length (including
  the appended ellipsis) does not exceed `AIOBS_SUMMARY_MAX_CHARS`, and it
  ends with an ellipsis

#### Scenario: Entry with no description yields empty summary

- GIVEN a feed entry with no description/summary field
- WHEN parsed
- THEN the stored summary is an empty string and rendering degrades to a
  title-only line with no blank summary line

#### Scenario: Zero max_chars yields empty summary

- GIVEN `AIOBS_SUMMARY_MAX_CHARS` is `0`
- WHEN any entry is parsed
- THEN the stored summary is an empty string regardless of the raw content
