# feed-collection Specification

## Purpose

Fetch RSS/Atom feeds over HTTP and parse them into normalized entries, isolating
per-source failures so a single dead or malformed feed never aborts the run.

## Requirements

### Requirement: Feed Fetching
The system MUST fetch each source's feed URL via HTTP using the configured User-Agent.

#### Scenario: Successful fetch
- GIVEN a source with a reachable feed URL
- WHEN the source is fetched
- THEN the raw response bytes are returned for parsing

#### Scenario: Fetch failure does not raise
- GIVEN a source whose URL times out or returns an HTTP error
- WHEN the source is fetched
- THEN the failure is caught, logged, and no exception propagates to the caller

### Requirement: Feed Parsing
The system MUST parse fetched feed bytes into zero or more normalized entries
(title, url, published_at, summary, raw source data).

#### Scenario: Well-formed feed parses
- GIVEN well-formed RSS or Atom bytes
- WHEN parsed
- THEN one entry is returned per feed item with title and url populated

#### Scenario: Malformed feed yields no entries
- GIVEN unparseable or malformed feed bytes
- WHEN parsed
- THEN zero entries are returned, no exception propagates, and the failure is logged

### Requirement: Per-Source Failure Isolation
A single source's fetch or parse failure MUST be logged and skipped, and MUST NOT
abort collection for the remaining sources.

#### Scenario: One dead feed among many
- GIVEN nine configured sources where one is unreachable
- WHEN collection runs
- THEN items from the eight healthy sources are collected, the run completes, and
  the dead source's failure is logged

### Requirement: Published-Date Normalization
The system MUST normalize `published_at` to UTC: tz-aware timestamps convert to
UTC; naive timestamps are assumed UTC; missing or unparseable timestamps default
to `collected_at` (also UTC).

#### Scenario: Timezone-aware date converts to UTC
- GIVEN an entry with a published date in a non-UTC timezone
- WHEN normalized
- THEN `published_at` is stored as the equivalent UTC instant

#### Scenario: Naive date assumed UTC
- GIVEN an entry with a timezone-naive published date
- WHEN normalized
- THEN `published_at` equals that date treated as UTC

#### Scenario: Missing date defaults to collected_at
- GIVEN an entry with no parseable published date
- WHEN normalized
- THEN `published_at` equals `collected_at`

### Requirement: User-Agent Identification
Every outbound HTTP request MUST include a configured, non-default User-Agent header.

#### Scenario: Request carries configured UA
- GIVEN the configured USER_AGENT value
- WHEN any source is fetched
- THEN the outbound request's User-Agent header equals the configured value
