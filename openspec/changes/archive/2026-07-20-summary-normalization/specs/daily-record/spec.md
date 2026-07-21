# Delta for daily-record

## MODIFIED Requirements

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
- THEN the line matches `- [title](url) — OpenAI (P1) · 14:05 UTC` followed
  by the summary
