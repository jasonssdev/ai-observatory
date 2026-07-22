# Delta for collect-cli

## ADDED Requirements

### Requirement: Live Progress Feedback
`collect` MUST display live progress feedback during both the source-collection phase (as sources are being fetched) and the LLM-classification phase (as items are being classified). Progress feedback is rendered via `typer.progressbar` and MUST degrade gracefully in non-TTY contexts (the bars are silent when stdout is not a terminal).

#### Scenario: Collection phase displays source name
- GIVEN `collect` is run in a terminal with reachable feeds
- WHEN the source-collection phase executes
- THEN a progress bar labeled "Collecting" displays, showing the current source being fetched by name

#### Scenario: Classification phase shows item count
- GIVEN items have been collected and deduplicated
- WHEN the classification phase executes
- THEN a progress bar labeled "Classifying" displays, advancing once per item classified (deterministic or LLM)

#### Scenario: Progress degrades gracefully in non-TTY
- GIVEN `collect` is invoked with stdout redirected to a file or pipe (non-TTY)
- WHEN `collect` runs
- THEN the progress bars are silent; the end-of-run summary, per-source warnings, and logging remain visible

#### Scenario: Behavior unchanged when progress is not rendered
- GIVEN the progress bars do not render (non-TTY, or testing environments where progress is disabled)
- WHEN `collect` runs
- THEN the collected/deduped/classified item counts, verdicts, and all other behavior remain identical to runs where progress bars are visible
