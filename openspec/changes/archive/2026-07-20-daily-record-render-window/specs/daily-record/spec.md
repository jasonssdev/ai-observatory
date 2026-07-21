# Delta for daily-record

## MODIFIED Requirements

### Requirement: Full Regeneration from DB (Idempotency)
Each run MUST regenerate (overwrite, never append) the Markdown file for
every published-date within `AIOBS_RECORD_WINDOW_DAYS` days of the run's
UTC date, plus the run's UTC date itself, computed entirely from current DB
contents. The underlying DB MUST retain every ingested item regardless of
the window — ingestion is unbounded; only the set of regenerated Markdown
files is bounded.
(Previously: regenerated every published-date present in the collected
batch plus the run's UTC date, with no window bound.)

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
