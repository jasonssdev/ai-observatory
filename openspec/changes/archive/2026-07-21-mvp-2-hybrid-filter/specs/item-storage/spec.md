# Delta for item-storage

## ADDED Requirements

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
