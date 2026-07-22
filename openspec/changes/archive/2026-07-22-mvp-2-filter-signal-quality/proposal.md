# Proposal: MVP-2 Filter Signal Quality

## Intent

The hybrid filter classifies but does not discriminate: a live `collect` run
(`mistral:7b`) marked 779/787 items SIGNIFICANT (99%). Keeping 99% is not
filtering — the digest is noise. Root cause: `parse_verdict` substring-matches
`"significant"`, which is also inside "not significant" and "insignificant",
so negating/verbose model output is misread as SIGNIFICANT. A weak prompt and
INFO-level `httpx` log flooding compound the problem.

## Root Cause

- `filter.py:parse_verdict` substring match misreads negations as SIGNIFICANT.
- `filter.py:build_prompt` gives no rubric, so the model rambles.
- `cli.py:73` `logging.basicConfig(INFO)` floods the console with httpx lines,
  burying the run summary.

## Scope

### In Scope
- Harden `parse_verdict`: first-token / word-boundary, negation-aware; ROUTINE
  safe default for ambiguous/empty.
- Tighten `build_prompt`: SIGNIFICANT/ROUTINE rubric + strict one-word output.
- Quiet logs: raise `httpx`/`httpcore` to WARNING (or scope INFO to
  `ai_observatory.*`); keep app INFO, summary, and per-source warnings.

### Out of Scope
- Ollama `format`/structured-output adapter (possible future hardening).
- Deterministic rules (P1 auto-keep, score-keep, noise keywords) — unchanged.
- Classification scope, new sources, weekly briefing, scheduling.

## Capabilities

### New Capabilities
None

### Modified Capabilities
- `hybrid-filter`: replace **Tolerant Parsing with Safe Default** (currently
  mandates substring match) with robust, negation-aware, first-token parsing;
  extend **LLM Verdict for Uncertain Items** to note the rubric + one-word
  prompt contract.
- `collect-cli`: extend **End-of-Run Summary** / **Per-Source Failure
  Visibility** to note third-party (httpx/httpcore) log suppression so the
  summary stays visible.

## Approach

Three focused edits in `filter.py` (parser + prompt) and `cli.py` (logging
config). Parser becomes token/word-boundary based with explicit negation
handling; prompt gains an operator-tunable rubric and a hard one-word
instruction; logging silences noisy third-party loggers while preserving app
INFO. Exact parsing algorithm pinned in design.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/filter.py` | Modified | `parse_verdict`, `build_prompt` |
| `src/ai_observatory/cli.py` | Modified | logging config (silence httpx/httpcore) |
| tests | Modified | parser regression cases, prompt content, logging assertion |

## Testing Plan (Strict TDD — `uv run pytest`)

`parse_verdict`: "SIGNIFICANT"→SIG; "ROUTINE"→ROUTINE; "This is not
significant"→ROUTINE (regression); "insignificant"→ROUTINE; leading
"SIGNIFICANT — because X"→SIG; empty/garbage→ROUTINE; mixed-case/whitespace.
`build_prompt`: includes rubric + one-word instruction + item title/summary.
Logging: app summary still prints and httpx logger level is raised — assert
deterministically via config, not captured third-party logs.

**Final signal quality is judged by real-run validation (operator tuning
loop), not by tests.** Tests lock the regression cases; the rubric is tuned
against real runs until output "feels right".

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| New parser over-corrects (too many ROUTINE) | Med | Real-run tuning loop; ROUTINE stays the safe default |
| Rubric wording biases the model | Med | Rubric is operator-tunable; not frozen in spec |
| Silencing logs hides a real error | Low | Only raise third-party loggers; keep app INFO + warnings |

## Rollback Plan

Revert the three edits (single small PR); deterministic rules and scope are
untouched, so reverting restores prior behavior with no data/migration impact.

## Dependencies

None new. Uses existing Ollama `LLMClient` and plain-text responses.

## Success Criteria

- [ ] "not significant" / "insignificant" classify as ROUTINE.
- [ ] A real `collect` run sets aside a materially larger share than 1%.
- [ ] Console shows the run summary without httpx flood.
- [ ] All new parser/prompt/logging tests pass; `uv run ruff check .` clean.

## Delivery Forecast

Size: **small** (3 files, focused). 400-line budget risk: **Low**.
Single PR expected.
