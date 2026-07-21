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
