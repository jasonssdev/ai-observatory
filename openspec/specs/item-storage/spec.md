# item-storage Specification

## Purpose

Persist collected items in SQLite as the durable source of truth, writing
idempotently so repeated runs never duplicate data.

## Requirements

### Requirement: Items Table as Source of Truth
The system MUST persist collected items in an `items` table including id,
title, url, canonical_url, title_hash, source, category, priority,
published_at, collected_at, summary, and raw.

#### Scenario: Successful collection persists a row
- GIVEN a normalized, deduplicated item
- WHEN it is written
- THEN a row exists in `items` with all listed fields populated

### Requirement: Idempotent Upsert
Writes MUST use an insert-or-ignore keyed on `id`, so writing a previously
stored id creates no duplicate row and raises no error.

#### Scenario: Duplicate id within a batch
- GIVEN two items resolving to the same id in one write batch
- WHEN both are written
- THEN exactly one row exists for that id

#### Scenario: Re-run with unchanged feeds adds no rows
- GIVEN a prior run already stored a source's current items
- WHEN collection re-runs against the same feed content
- THEN zero new rows are inserted for that source

### Requirement: Raw Entry Preservation
The original feed entry MUST be stored as JSON text in the `raw` column.

#### Scenario: Raw column round-trips as JSON
- GIVEN a stored item
- WHEN the `raw` column is parsed as JSON
- THEN it decodes successfully and represents the source feed entry

### Requirement: Query by Published Date
Storage MUST support retrieving all items whose `published_at` falls within a
given UTC calendar day.

#### Scenario: Query returns only matching-day items
- GIVEN items with published_at spanning two different UTC days
- WHEN querying for one of those days
- THEN only items published on that UTC day are returned

### Requirement: Item Significance Table
The system MUST persist significance verdicts in an `item_significance`
table (item id as foreign key to `items`, verdict label, classification
method, and model name when applicable), created idempotently via
`CREATE TABLE IF NOT EXISTS`. The `items` table itself MUST remain
unmodified by this addition.

#### Scenario: Table creation is idempotent
- GIVEN a DB connection is opened multiple times against the same file
- WHEN storage initialization runs each time
- THEN no error occurs and exactly one `item_significance` table exists

### Requirement: Idempotent Verdict Upsert
Writing a significance verdict for an item id MUST use an insert-or-update
keyed on item id, so writing a verdict for an already-classified item
updates the existing row rather than creating a duplicate.

#### Scenario: Re-run does not duplicate a verdict
- GIVEN an item already has a persisted verdict
- WHEN a verdict for the same item id is written again
- THEN exactly one row exists for that item id in `item_significance`

### Requirement: Query Significance by Date and Item
Storage MUST support querying significance verdicts for items published on
a given UTC calendar day, and looking up the verdict for a single item id.

#### Scenario: Query returns verdicts for matching-day items
- GIVEN items with verdicts spanning two different UTC published days
- WHEN querying significance for one of those days
- THEN only verdicts for items published on that UTC day are returned

#### Scenario: Query by item id returns its verdict
- GIVEN an item with a persisted verdict
- WHEN querying significance by that item's id
- THEN the stored verdict is returned

### Requirement: Query Unclassified Items Within a Window
Storage MUST support retrieving all items whose `published_at` falls within
a given date range (inclusive start and end) and that have no persisted
significance verdict, mirroring `unclassified_for_date` but scoped to a
window instead of a single UTC calendar day.

#### Scenario: Window query returns unclassified in-range items
- GIVEN items with `published_at` spanning several UTC days, none of them
  yet classified
- WHEN querying unclassified items for a window range covering a subset of
  those days
- THEN exactly the items whose `published_at` falls within the range are
  returned

#### Scenario: Already-classified and out-of-range items are excluded
- GIVEN an item within the range that already has a persisted verdict, and
  an item outside the range with no verdict
- WHEN querying unclassified items for that range
- THEN neither item is returned
