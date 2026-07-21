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
every published-date present in the collected batch plus the run's UTC date,
computed entirely from current DB contents.

#### Scenario: Re-run with no new items is stable
- GIVEN a record already generated for a day with no new items collected
- WHEN collection re-runs
- THEN the regenerated file contains the same items exactly once each, no duplicates

#### Scenario: Re-run with one new item for the day
- GIVEN a record already generated for a day, and one new item for that day is stored
- WHEN collection re-runs
- THEN the regenerated file contains the new item exactly once alongside prior items

### Requirement: Item Line Format
Each item MUST render as `- [title](url) — source (Pn) · HH:MM UTC` followed
by its summary, if present.

#### Scenario: Item renders in expected format
- GIVEN an item with priority 1, source "OpenAI", published_at 14:05 UTC
- WHEN rendered
- THEN the line matches `- [title](url) — OpenAI (P1) · 14:05 UTC` followed by the summary
