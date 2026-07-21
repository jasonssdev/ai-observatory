# daily-record Specification

## Purpose

Render a readable, fully-reproducible Markdown daily record from the DB for
each affected UTC calendar day.

## Requirements

### Requirement: Markdown Record Generation
For a UTC calendar day, the system MUST render `data/records/<YYYY-MM-DD>.md`
containing every item whose `published_at` falls on that day, with a header
stating the date and item count.

#### Scenario: Day with items produces a populated file
- GIVEN three stored items published on the same UTC day
- WHEN the record for that day is generated
- THEN the file header states the date and count 3, with one rendered entry per item

### Requirement: Category Grouping and Priority Sort
Items MUST be grouped by category; within each group, sorted by source
priority ascending, then `published_at` descending.

#### Scenario: Mixed categories and priorities render ordered
- GIVEN items across two categories, each with two priorities
- WHEN rendered
- THEN items are grouped by category and, within each group, ordered by
  priority ascending then published_at descending

### Requirement: Full Regeneration from DB (Idempotency)
Each run MUST regenerate (overwrite, never append) the Markdown file for
every published-date within `AIOBS_RECORD_WINDOW_DAYS` days of the run's
UTC date, plus the run's UTC date itself, computed entirely from current DB
contents. The underlying DB MUST retain every ingested item regardless of
the window — ingestion is unbounded; only the set of regenerated Markdown
files is bounded.

#### Scenario: Re-run with no new items is stable
- GIVEN a record already generated for a day within the window, with no new
  items collected
- WHEN collection re-runs
- THEN the regenerated file contains the same items exactly once each, no
  duplicates

#### Scenario: Re-run with one new item for the day
- GIVEN a record already generated for a day within the window, and one new
  item for that day is stored
- WHEN collection re-runs
- THEN the regenerated file contains the new item exactly once alongside
  prior items

#### Scenario: Cold-start backlog stays bounded
- GIVEN the DB holds items published across many years, including dates far
  outside the window
- WHEN collection runs
- THEN Markdown files are generated only for published-dates within the
  window plus the run's UTC date, not for the out-of-window historical
  dates

#### Scenario: Window of zero renders only today
- GIVEN `AIOBS_RECORD_WINDOW_DAYS` is `0`
- WHEN collection runs
- THEN only the record file for the run's UTC date is generated

#### Scenario: Run date is always rendered
- GIVEN no stored items have a `published_at` within the window
- WHEN collection runs
- THEN the record file for the run's UTC date is still generated

### Requirement: Item Line Format
Each item MUST render as `- [title](url) — source (Pn) · HH:MM UTC` followed
by its summary, if present. The rendered summary MUST be the normalized
plain-text `summary` produced by feed parsing (see `feed-collection`); this
requirement governs line layout only and introduces no change to render
format or to "if present" behavior.
(Previously: no explicit statement that the rendered summary is the
normalized plain-text value; render format itself is unchanged by this
clarification.)

#### Scenario: Item renders in expected format
- GIVEN an item with priority 1, source "OpenAI", published_at 14:05 UTC
- WHEN rendered
- THEN the line matches `- [title](url) — OpenAI (P1) · 14:05 UTC` followed by the summary
