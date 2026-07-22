# Design: MVP-2 Filter Signal Quality

## Technical Approach

Three focused, pure edits fix a filter that classified 99% of items SIGNIFICANT
(proposal `sdd/mvp-2-filter-signal-quality/proposal`). No new dependencies, no
I/O, no scope change. `parse_verdict` moves from substring match to
negation-aware word-boundary tokenization; `build_prompt` gains a compact rubric
and a strict one-word contract; `cli.collect` extracts a `_configure_logging`
seam that silences third-party HTTP noise while preserving the app summary and
per-source warnings.

## Architecture Decisions

### Decision: Robust `parse_verdict` parsing strategy

**Choice**: Tokenize on word boundaries, scan for the first decisive token
(`significant`/`routine`), apply negation lookback, default ROUTINE.
**Alternatives considered**: (a) keep substring match — the root bug; (b) Ollama
structured-output/`format` — explicit non-goal, larger surface.
**Rationale**: Word-boundary tokenization excludes `insignificant` as a distinct
token for free; negation lookback fixes "not significant"; pure and never-raises
keeps the existing degrade-safe contract intact.

### Decision: Logging suppression via named third-party loggers

**Choice**: Keep `basicConfig(level=INFO)`, then raise `httpx` and `httpcore`
loggers to WARNING inside a `_configure_logging()` helper.
**Alternatives considered**: root at WARNING + `ai_observatory` at INFO. Silences
all third-party INFO in one move but leaves `httpx.level == NOTSET`, so a test
must assert `getEffectiveLevel()` rather than `.level`.
**Rationale**: Option A is the minimal targeted fix matching the proposal ("only
third-party loggers raised"), keeps root INFO for any future app INFO logs, and
yields a crisp deterministic assertion on `httpx.level == WARNING`. App summary
is `typer.echo` (stdout) and per-source `logger.warning` (level WARNING) — both
surface regardless.

## Data Flow

    LLM response.text ──▶ parse_verdict ──▶ Verdict (SIGNIFICANT|ROUTINE)
                            │ lower + re.findall([a-z']+)
                            │ first decisive token, negation lookback
                            └ default ROUTINE

    collect() ──▶ _configure_logging() ──▶ httpx/httpcore = WARNING
                                            app INFO + summary + warnings kept

## Interfaces / Contracts

`parse_verdict` (pinned control flow):

```python
import re

_DECISIVE = {"significant": Verdict.SIGNIFICANT, "routine": Verdict.ROUTINE}
_NEGATIONS = {"not", "no", "non", "isn't", "isnt"}

def parse_verdict(text: str) -> Verdict:
    tokens = re.findall(r"[a-z']+", text.lower())
    for i, tok in enumerate(tokens):
        if tok == "significant":
            if i > 0 and tokens[i - 1] in _NEGATIONS:
                return Verdict.ROUTINE
            return Verdict.SIGNIFICANT
        if tok == "routine":
            return Verdict.ROUTINE
    return Verdict.ROUTINE
```

Case resolution: `"SIGNIFICANT"`→SIG; `"ROUTINE"`→ROU; `"not significant, it's
routine"`→ROU (first decisive token `significant` at i=1, prev `not`→ROU);
`"insignificant"`→ROU (single token `insignificant` ≠ `significant`, no match →
default); `"SIGNIFICANT — major release"`→SIG (i=0, no prev); `""`/garbage→ROU
(empty/no decisive token). Never raises; `[a-z']+` keeps `isn't` intact for
negation lookback.

`build_prompt` (pinned single f-string, operator-tunable rubric):

```python
def build_prompt(item: Item) -> str:
    return (
        "You are an editor triaging AI news for a daily digest.\n"
        "Classify the item as SIGNIFICANT or ROUTINE.\n"
        "SIGNIFICANT = major model or product release, research breakthrough, "
        "or important policy, safety, or funding news with real impact.\n"
        "ROUTINE = incremental updates, tutorials, opinion or commentary, "
        "roundups or newsletters, and minor releases.\n\n"
        f"Title: {item.title}\n"
        f"Summary: {item.summary}\n\n"
        "Answer with ONLY one word: SIGNIFICANT or ROUTINE."
    )
```

`_configure_logging` (new pure seam in `cli.py`):

```python
def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

`collect()` replaces its inline `basicConfig` call with `_configure_logging()`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/synthesis/filter.py` | Modify | Add `import re`; rewrite `parse_verdict` (negation-aware tokenizer) and `build_prompt` (rubric + one-word instruction) |
| `src/ai_observatory/cli.py` | Modify | Extract `_configure_logging()`; call it from `collect()`; raise httpx/httpcore to WARNING |
| `tests/unit/test_filter.py` | Modify | Add `parse_verdict` case table + `build_prompt` substring assertions |
| `tests/unit/test_cli.py` | Create | Assert `_configure_logging()` sets `logging.getLogger("httpx").level == WARNING` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `parse_verdict` all mandatory cases + mixed-case/whitespace | Direct calls, assert `Verdict`, pure |
| Unit | `build_prompt` content | Assert substrings: `SIGNIFICANT`, `ROUTINE`, `breakthrough`, `tutorials`, `roundups`, `Answer with ONLY one word`, item title/summary |
| Unit | Logging suppression | Call `_configure_logging()`, assert `logging.getLogger("httpx").level == logging.WARNING` and `httpcore` likewise — deterministic, not captured logs |

Strict TDD: RED tests first (`uv run pytest`), then implement, then
`uv run ruff check .`. Real signal quality is tuned by the operator loop, not
locked by tests; tests lock regression cases only.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. Logging config sets in-process
logger levels only.

## Migration / Rollout

No migration required. Three-file edit, single small PR; deterministic rules,
sources, and scope untouched; no data or schema impact. Rollback = revert.

## Open Questions

- None blocking. Rubric wording and negation set are operator-tunable and
  expected to be refined against real collect runs.
