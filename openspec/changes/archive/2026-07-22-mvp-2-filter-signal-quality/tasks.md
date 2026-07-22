# Tasks: MVP-2 Filter Signal Quality

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~150-200 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Fix filter signal quality (parser, prompt, logging) | PR 1 | `uv run pytest tests/unit/test_filter.py tests/unit/test_cli.py` | N/A — pure/unit-level change, no live LLM/network harness required | `git revert` of the single PR; no schema/data touched |

## Phase 1: RED — `parse_verdict` case table

- [x] 1.1 In `tests/unit/test_filter.py`, review existing `TestParseVerdict`/`TestParseVerdictMalformedDefault` cases: confirm none codify the substring bug (checked — `test_substring_match_within_longer_sentence` asserts `"Verdict: SIGNIFICANT."` → SIGNIFICANT, which the new word-boundary logic still resolves to SIGNIFICANT since `verdict` isn't a negation; no rename/flip required).
- [x] 1.2 Add failing case `"not significant, it's routine"` → `Verdict.ROUTINE` (regression case for the substring bug).
- [x] 1.3 Add failing case `"insignificant"` → `Verdict.ROUTINE`.
- [x] 1.4 Add failing case `"SIGNIFICANT — major model release"` (leading word, trailing text) → `Verdict.SIGNIFICANT`.
- [x] 1.5 Confirm exact `"SIGNIFICANT"` and exact `"ROUTINE"` cases exist (already covered) and empty/garbage default cases exist (already covered).
- [x] 1.6 Run `uv run pytest tests/unit/test_filter.py -k ParseVerdict` and confirm 1.2-1.4 fail (RED) against current substring implementation.

## Phase 2: GREEN — `parse_verdict` rewrite

- [x] 2.1 In `src/ai_observatory/synthesis/filter.py`, add `import re` and rewrite `parse_verdict` per design: `re.findall(r"[a-z']+", text.lower())`, scan for first decisive token (`significant`/`routine`), negation lookback against `{"not","no","non","isn't","isnt"}`, default `Verdict.ROUTINE`. Pure, never raises.
- [x] 2.2 Run `uv run pytest tests/unit/test_filter.py -k ParseVerdict` and confirm all cases (1.2-1.5) pass (GREEN).

## Phase 3: RED/GREEN — `build_prompt` rubric

- [x] 3.1 In `tests/unit/test_filter.py`, extend `TestBuildPrompt` with failing assertions for rubric substrings: `"breakthrough"`, `"tutorials"`, `"roundups"`, and `"Answer with ONLY one word"` (title/summary/SIGNIFICANT/ROUTINE already covered).
- [x] 3.2 Run `uv run pytest tests/unit/test_filter.py -k BuildPrompt` and confirm 3.1 fails (RED).
- [x] 3.3 In `src/ai_observatory/synthesis/filter.py`, rewrite `build_prompt` per design's pinned f-string (rubric + one-word instruction).
- [x] 3.4 Run `uv run pytest tests/unit/test_filter.py -k BuildPrompt` and confirm pass (GREEN).

## Phase 4: RED/GREEN — Logging seam

- [x] 4.1 Create `tests/unit/test_cli_logging.py` (renamed from planned `test_cli.py` — see deviation note); write a failing test that imports `_configure_logging` from `ai_observatory.cli`, calls it, and asserts `logging.getLogger("httpx").level == logging.WARNING` and `logging.getLogger("httpcore").level == logging.WARNING`.
- [x] 4.2 Run `uv run pytest tests/unit/test_cli_logging.py` and confirm RED (`_configure_logging` does not exist yet).
- [x] 4.3 In `src/ai_observatory/cli.py`, extract `_configure_logging()` (keep `logging.basicConfig(level=logging.INFO)`, add `logging.getLogger("httpx").setLevel(logging.WARNING)` and `logging.getLogger("httpcore").setLevel(logging.WARNING)`); replace the inline `basicConfig` call in `collect()` with `_configure_logging()`.
- [x] 4.4 Run `uv run pytest tests/unit/test_cli_logging.py` and confirm GREEN.

## Phase 5: Final Gates

- [x] 5.1 Run full `uv run pytest` and confirm all tests green (including unaffected suites). Result: 191 passed (baseline 186 + 5 new).
- [x] 5.2 Run `uv run ruff check .` and confirm clean. Result: All checks passed.
- [x] 5.3 Cross-check every scenario in `openspec/changes/mvp-2-filter-signal-quality/specs/hybrid-filter/spec.md` and `specs/collect-cli/spec.md` has a corresponding passing test (parsing 7 cases, prompt content, logging levels, summary/warning visibility unchanged). Confirmed — see apply-progress artifact.
