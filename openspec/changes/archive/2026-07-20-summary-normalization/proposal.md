# Proposal: Summary Normalization

## Intent

`Item.summary` is stored VERBATIM from the feed at `rss.py:124`, so HTML tags,
entities, and trailing "Tags:/Via:" blocks leak into stored and rendered
summaries — violating the documented contract `docs/architecture.md:91`
("Short text from the feed"). Normalize summaries to short, clean plain text.
Pure transform, no LLM, no new dependency.

## Scope

### In Scope
- New pure module `collection/text.py` — `normalize_summary(raw_summary, max_chars) -> str`.
- Pipeline: first-paragraph extract → strip tags + unescape → `.strip()` → truncate w/ ellipsis.
- Config `AIOBS_SUMMARY_MAX_CHARS` (default 500), mirroring `record_window_days`.
- Thread `summary_max_chars` explicitly into `parse_feed` (keeps it pure).
- Spec deltas: `feed-collection` (Feed Parsing) + `collect-cli` (new env var); light `daily-record` clarification.

### Out of Scope
- Migration/backfill of already-stored dirty rows (`INSERT OR IGNORE`; reset via `rm -rf data`).
- LLM summarization; render-format changes; dedup/storage/ordering/grouping changes.
- "Prefer summary over content" — confirmed NOT actionable (exploration Finding 1).
- Touching `raw` (full-entry safety net, `rss.py:127`).

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `feed-collection`: Feed Parsing now yields NORMALIZED summaries (HTML stripped, first paragraph only, length-capped with ellipsis, whitespace-only → empty).
- `collect-cli`: document `AIOBS_SUMMARY_MAX_CHARS` (default 500, invalid/negative → default).
- `daily-record`: light clarification only — "summary if present (non-empty after normalization)". No behavior change.

## Approach

Add a pure `normalize_summary` in `collection/text.py`. Order (exploration Finding 4):
1. Extract first paragraph — HTML `</p>` boundary, else blank-line split, else whole string.
2. Strip tags via a tolerant `html.parser.HTMLParser` subclass (never raises) + entity unescape (Finding 3).
3. `.strip()` — whitespace-only ⇒ `""` (Finding 8; keeps render clean).
4. Truncate to `max_chars` with ellipsis; ellipsis counts toward cap (total ≤ max_chars).

Config mirrors `record_window_days` exactly (`_DEFAULT_SUMMARY_MAX_CHARS = 500`, `_int_env`). Call the helper at `rss.py:124` with `max_chars` threaded from `RssCollector`/config through `parse_feed`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/collection/text.py` | New | Pure `normalize_summary` + HTMLParser stripper |
| `src/ai_observatory/collection/rss.py` | Modified | Call helper at :124; thread `max_chars` into `parse_feed`/`RssCollector` |
| `src/ai_observatory/config.py` | Modified | `summary_max_chars` field + `from_env` wiring |
| `openspec/specs/feed-collection/spec.md` | Modified | Normalized-summary scenarios |
| `openspec/specs/collect-cli/spec.md` | Modified | `AIOBS_SUMMARY_MAX_CHARS` |
| `openspec/specs/daily-record/spec.md` | Modified | Light clarification |
| `tests/` + XML fixtures | New | Unit tests + 3 offline feed fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `max_chars=0` / ellipsis underflow (cap < len ellipsis) | Med | Define `max_chars=0` ⇒ `""`; guard ellipsis so output never exceeds cap; test explicitly |
| Ellipsis-in-budget ambiguity | Med | Spec: total output ≤ `max_chars` (reserve room for `…`) |
| `parse_feed` signature change at collector seam | Med | Explicit `max_chars` param; keep `parse_feed` pure; update sole call site in `RssCollector` |
| Dirty rows not re-normalized (non-retroactive) | High | Operational note: `rm -rf data` then re-collect; NO migration |
| Whitespace-only truthy → blank indented line | Low | `.strip()` fold to falsy `""` (Finding 8) |
| Double entity unescape | Low | HTMLParser `convert_charrefs=True` decodes once |

## Rollback Plan

Revert the change commit. `raw` is untouched and `summary TEXT NOT NULL` schema is unchanged, so no schema rollback. Local dirty/normalized rows coexist harmlessly; `rm -rf data` fully resets if desired.

## Dependencies

- None (stdlib `html.parser` / `html.unescape` only).

## Success Criteria

- [ ] `normalize_summary` strips tags, unescapes entities, keeps first paragraph, caps length with ellipsis, folds whitespace-only → `""`.
- [ ] `AIOBS_SUMMARY_MAX_CHARS` respected; invalid/negative → 500.
- [ ] `parse_feed` stays pure; new items stored as clean plain text; `raw` unchanged.
- [ ] Existing `feed_valid.xml` short-summary assertion still passes (no regression).
- [ ] `max_chars=0` and tiny-cap ellipsis cases covered by tests.
