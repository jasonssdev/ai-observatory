# Delta for daily-record

## MODIFIED Requirements

### Requirement: Markdown Record Generation
For a UTC calendar day, the system MUST render `data/records/<YYYY-MM-DD>.md`
containing every item whose `published_at` falls on that day, with a header
stating the date, the total item count, and the run's filter mode
(`hybrid` when the LLM was available, `deterministic-only` when the run
degraded per the `hybrid-filter` fallback requirement).
(Previously: header stated only the date and item count, with no filter-mode
signal.)

#### Scenario: Day with items produces a populated file
- GIVEN three stored items published on the same UTC day, classified via
  hybrid filtering
- WHEN the record for that day is generated
- THEN the file header states the date, count 3, and `(filter: hybrid)`

#### Scenario: Header signals deterministic-only mode
- GIVEN items classified during a run where the LLM was unavailable
- WHEN the record for that day is generated
- THEN the file header states `(filter: deterministic-only — LLM
  unavailable)`

### Requirement: Category Grouping and Priority Sort
Within the `## Significant` bucket, items MUST be grouped by category;
within each group, sorted by source priority ascending, then
`published_at` descending. The `## Set aside` bucket is not category
grouped.
(Previously: applied to the single flat item list with no bucket
distinction.)

#### Scenario: Mixed categories and priorities render ordered
- GIVEN significant items across two categories, each with two priorities
- WHEN rendered
- THEN items in `## Significant` are grouped by category and, within each
  group, ordered by priority ascending then published_at descending

## ADDED Requirements

### Requirement: Two-Bucket Significance Rendering
The record MUST render two sections in order: `## Significant` containing
items classified `SIGNIFICANT`, and `## Set aside` containing items
classified `ROUTINE`. Each section MUST render (with its header) even when
it contains zero items for that day.

#### Scenario: Both buckets populated
- GIVEN a day with both significant and routine items
- WHEN the record is generated
- THEN `## Significant` lists the significant items and `## Set aside`
  lists the routine items

#### Scenario: Empty bucket still renders its header
- GIVEN a day with only significant items and zero routine items
- WHEN the record is generated
- THEN `## Set aside` still renders as an empty section

### Requirement: Set-Aside Compact Rendering
Items in `## Set aside` MUST render one compact line per item (title, url,
source, priority, time), omitting the summary body rendered for
significant items.

#### Scenario: Routine item renders without summary
- GIVEN a routine item with a non-empty summary
- WHEN rendered in `## Set aside`
- THEN the line matches the standard item-line format with no summary text
  beneath it
