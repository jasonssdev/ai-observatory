# Delta for item-storage

## ADDED Requirements

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
