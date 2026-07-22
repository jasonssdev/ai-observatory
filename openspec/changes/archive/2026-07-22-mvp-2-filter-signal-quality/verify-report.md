# Verify Report: MVP-2 Filter Signal Quality

**Change**: `mvp-2-filter-signal-quality`
**Mode**: Full artifact set (proposal/spec/design/tasks/apply-progress) — Strict TDD
**Verdict**: PASS WITH WARNINGS

## Completeness

All 17 tasks in `openspec/changes/mvp-2-filter-signal-quality/tasks.md` are checked `[x]` and each maps to real, inspected code and a passing test. No unchecked tasks.

## Build/Test Evidence (run by this verify phase, not trusted from apply-progress alone)

- `uv run pytest` → **191 passed**, 0 failed (baseline 186 + 5 new: 2 negation, 1 leading-word-trailing-text, 1 rubric, 1 logging). Matches apply-progress claim.
- `uv run ruff check .` → **All checks passed.**

## Parser Fix — Rigorous Check (the core of this change)

`parse_verdict` in `src/ai_observatory/synthesis/filter.py` (lines 124-147):

```python
_NEGATIONS = {"not", "no", "non", "isn't", "isnt"}

def parse_verdict(text: str) -> Verdict:
    tokens = re.findall(r"[a-z']+", text.lower())
    for i, token in enumerate(tokens):
        if token == "significant":
            if i > 0 and tokens[i - 1] in _NEGATIONS:
                return Verdict.ROUTINE
            return Verdict.SIGNIFICANT
        if token == "routine":
            return Verdict.ROUTINE
    return Verdict.ROUTINE
```

Confirmed NOT a substring match (`"significant" in text` is gone) — uses `re.findall(r"[a-z']+", ...)` word-boundary tokenization. Pure function, no I/O, no branch that raises (regex + set lookups only) → never raises, confirmed by code inspection.

Case-by-case (code trace + covering test, both checked):
| Input | Expected | Code trace | Test |
|---|---|---|---|
| `"SIGNIFICANT"` (case/whitespace variants: `"  Significant  "`) | SIGNIFICANT | token 0 = "significant", i=0, no prev → SIGNIFICANT | `test_significant_case_and_whitespace_tolerant` — PASS |
| `"ROUTINE"` (`"  ROUTINE\n"`) | ROUTINE | token 0 = "routine" → ROUTINE | `test_routine_case_and_whitespace_tolerant` — PASS |
| `"This is not significant, it's routine."` (regression case) | ROUTINE | tokens=[this,is,not,significant,...]; "significant" at i=3, tokens[2]="not" ∈ negations → ROUTINE | `test_negated_significant_is_routine` — PASS |
| `"insignificant"` | ROUTINE | single token "insignificant" ≠ "significant" (word-boundary excludes it) → falls through → ROUTINE | `test_insignificant_is_not_a_significant_token` — PASS |
| `"SIGNIFICANT — major model release"` (leading verdict, trailing text) | SIGNIFICANT | token 0 = "significant", i=0 → SIGNIFICANT | `test_leading_word_with_trailing_text` — PASS |
| `""` / `"I cannot decide."` (garbage) | ROUTINE | no decisive token found → loop exhausts → ROUTINE | `test_empty_string_defaults_to_routine`, `test_unparseable_text_defaults_to_routine` — PASS |
| `"Verdict: SIGNIFICANT."` (old substring-bug-adjacent case) | SIGNIFICANT | "verdict" not a negation, "significant" at i=1 → SIGNIFICANT (not a regression; correctly resolves under new logic too) | `test_substring_match_within_longer_sentence` — PASS |

Task 1.1 claim verified: no existing test codified the old substring bug — `test_substring_match_within_longer_sentence` passes under both the old (buggy) and new (fixed) implementation, so it required no flip.

**CRITICAL check**: parser does not raise, does not substring-match, and `"not significant"` correctly resolves ROUTINE. No CRITICAL issue found here.

## Prompt Check

`build_prompt` (filter.py lines 150-167) is a single f-string containing: significance rubric (SIGNIFICANT = major model/product release, research breakthrough, policy/safety/funding; ROUTINE = incremental updates, tutorials, opinion/commentary, roundups/newsletters, minor releases), a strict `"Answer with ONLY one word: SIGNIFICANT or ROUTINE."` instruction, and `item.title`/`item.summary` interpolation. Confirmed via code and via `test_prompt_contains_rubric_and_one_word_instruction` + `test_prompt_contains_title_summary_and_instruction` (both PASS, asserting `"breakthrough"`, `"tutorials"`, `"roundups"`, `"Answer with ONLY one word"`, title, summary substrings).

## Logging Check

`_configure_logging()` (cli.py lines 70-80): `logging.basicConfig(level=logging.INFO)` + `logging.getLogger("httpx").setLevel(logging.WARNING)` + `logging.getLogger("httpcore").setLevel(logging.WARNING)`. `collect()` calls it at line 86 (first line of the command body).

- `logging.getLogger("httpx").level == logging.WARNING` and `httpcore` likewise: asserted by `tests/unit/test_cli_logging.py::TestConfigureLogging::test_httpx_and_httpcore_loggers_raised_to_warning` — PASS, deterministic level check (not scraped log output), matches Hard Rule "spec scenario compliant only when a covering test passed at runtime."
- App logger (`ai_observatory.*`) is never touched by `_configure_logging()`, so it inherits the root logger's `INFO` level set by `basicConfig`. Manually verified at runtime during this verify pass: `logging.getLogger("ai_observatory").getEffectiveLevel() == 20` (INFO) after calling `_configure_logging()`. **However, no test in the suite asserts this directly** — see WARNING below.
- Per-source `logger.warning(...)` (cli.py `logger = logging.getLogger(__name__)` = `"ai_observatory.cli"`) and the `typer.echo` summary both surface: confirmed by code (untouched by the two suppressed loggers) and by `tests/integration/test_collect_integration.py::TestPerSourceFailureVisibility` (caplog-based, PASS) and `TestRunSummary` (capsys-based, PASS) — both pre-existing/unchanged tests, still green.

## Spec Compliance Matrix

### hybrid-filter (`specs/hybrid-filter/spec.md`)
| Requirement | Scenario | Status |
|---|---|---|
| Tolerant Parsing with Safe Default | Malformed → ROUTINE | PASS (test) |
| | Exact SIGNIFICANT | PASS (test) |
| | Exact ROUTINE | PASS (test) |
| | Negated significance → ROUTINE | PASS (test) |
| | "insignificant" → ROUTINE | PASS (test) |
| | Leading verdict + trailing text → SIGNIFICANT | PASS (test) |
| | Empty → ROUTINE | PASS (test) |
| | Case/whitespace variants | PASS (test) |
| LLM Verdict for Uncertain Items | LLM SIGNIFICANT → item SIGNIFICANT | PASS (existing test, unchanged) |
| | LLM ROUTINE → item ROUTINE | PASS (existing test, unchanged) |
| | Prompt carries rubric + instruction + title/summary | PASS (test) |

### collect-cli (`specs/collect-cli/spec.md`)
| Requirement | Scenario | Status |
|---|---|---|
| End-of-Run Summary | Summary reflects real run counts | PASS (existing test, unchanged) |
| | Deterministic-only mode reported | PASS (existing test, unchanged) |
| | Third-party HTTP loggers suppressed to WARNING | PASS (test) |
| | App logger remains INFO+ alongside suppression | **WARNING — no dedicated runtime-asserted test; verified only by manual inspection during this verify pass** |
| Per-Source Failure Visibility | Failing source produces visible warning | PASS (existing test, unchanged) |
| | Source returning nothing distinguishable from crash | PASS (existing code path + `Sources returning nothing` summary line; existing test, unchanged) |

## Design Coherence

`parse_verdict`, `build_prompt`, and `_configure_logging` implementations match the pinned design interfaces in `design.md` verbatim, including the exact regex, negation set, and rubric wording. No deviation from the pinned interfaces.

## Issues

### CRITICAL
None.

### WARNING
1. **Untested spec scenario**: "Application logging remains visible alongside suppression" (collect-cli spec, `End-of-Run Summary` requirement) has no dedicated runtime-asserted test. Behavior is correct (manually verified: `ai_observatory` logger effective level stays `INFO` after `_configure_logging()`), but per the Hard Rule "a spec scenario is compliant only when a covering test passed at runtime," this scenario currently relies on inspection, not an executed assertion. Recommend adding `assert logging.getLogger("ai_observatory").getEffectiveLevel() <= logging.INFO` to `tests/unit/test_cli_logging.py`.

### SUGGESTION
1. **Stale work-unit doc reference**: `tasks.md`'s "Suggested Work Units" table (line 23) and the original Phase 4 task text still reference `tests/unit/test_cli.py` as the focused test command target; the actual file is `tests/unit/test_cli_logging.py` (renamed per the documented deviation in apply-progress). Running the table's literal command (`uv run pytest tests/unit/test_filter.py tests/unit/test_cli.py`) exits 4 ("file or directory not found") — verified during this pass. The rename is well-documented in task 4.1's completed checkbox text and apply-progress, but the summary table itself was not updated. Cosmetic only; recommend a follow-up edit to `tasks.md` line 23.

## Verdict

**PASS WITH WARNINGS** — 0 CRITICAL, 1 WARNING, 1 SUGGESTION. The parser regression fix (the whole point of this change) is correctly implemented, provably non-substring, negation-aware, and covered by passing tests for every mandated case. Safe to proceed to archive; the WARNING is a test-coverage gap on a low-risk, code-verified behavior and does not block archive, but should be tracked as a fast follow-up.
