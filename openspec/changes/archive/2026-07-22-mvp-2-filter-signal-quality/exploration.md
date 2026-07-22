# Exploration: MVP-2 Filter Signal Quality

## Trigger

Live MVP-2 validation. After the classification-scope fix, a real `collect`
run with `mistral:7b` classified **779 of 787 items SIGNIFICANT (99%)** — only
8 set aside. The filter runs but does not discriminate; keeping 99% is not
filtering.

## Root Cause (confirmed by reading source)

### Primary: naive substring parsing in `parse_verdict`
`src/ai_observatory/synthesis/filter.py:123-133`:
```python
normalized = text.strip().lower()
if "significant" in normalized:
    return Verdict.SIGNIFICANT
return Verdict.ROUTINE
```
Two compounding failures:
1. `mistral:7b` ignores "respond with one word" and answers verbosely
   (e.g. "This item is not significant, it's routine").
2. The substring `"significant"` is contained in **"not significant"** and
   **"insignificant"** — a NEGATIVE verdict still matches SIGNIFICANT.

Result: nearly every verbose/negating response is misread as SIGNIFICANT.

### Contributing: weak prompt in `build_prompt`
`filter.py:136-145` asks for one word but gives no rubric for what
SIGNIFICANT vs ROUTINE means and no strong steer, so the model rambles.

### Secondary: log noise
`src/ai_observatory/cli.py:73` sets `logging.basicConfig(level=logging.INFO)`,
enabling INFO for ALL loggers including `httpx`. The terminal floods with one
`INFO:httpx:HTTP Request:` line per fetch and per LLM call; the app's own
end-of-run summary is buried.

## Spec Surface Confirmed

- `openspec/specs/hybrid-filter/spec.md` — requirement **"Tolerant Parsing
  with Safe Default"** (lines 100-109) explicitly mandates substring matching.
  This is the requirement to MODIFY. Requirement **"LLM Verdict for Uncertain
  Items"** (84-98) covers the prompt contract.
- `openspec/specs/collect-cli/spec.md` — **"End-of-Run Summary"** (128-146)
  and **"Per-Source Failure Visibility"** (148-165) require operator-visible
  output; third-party log suppression extends these.

## Proposed Fix (three parts)

1. **Harden `parse_verdict`**: first-meaningful-token / word-boundary match,
   negation-aware. Property: "not significant" and "insignificant" → ROUTINE;
   leading "SIGNIFICANT" → SIGNIFICANT; empty/ambiguous → ROUTINE (safe
   default). Exact algorithm pinned in design.
2. **Tighten `build_prompt`**: short SIGNIFICANT/ROUTINE rubric + strict
   single-word instruction. Rubric is an operator-tunable starting point.
3. **Quiet logs**: raise `httpx`/`httpcore` loggers to WARNING (or scope INFO
   to `ai_observatory.*`); keep app INFO + summary + per-source warnings.

## Key Decisions

1. Robust verdict parsing (first-word/word-boundary + negation-aware), not
   substring.
2. Prompt rubric + strict one-word output.
3. Silence httpx/httpcore INFO; keep app INFO + summary.
4. Safe default remains ROUTINE.
5. Ollama structured-output (`format`) passthrough is OPTIONAL / OUT OF SCOPE
   (possible future hardening); the parser must work on plain text first.
6. Final signal quality is judged by a real-run tuning loop, not just unit
   tests.

## Out of Scope

No Ollama `format`/structured-output adapter; no change to deterministic
rules (P1 auto-keep, score-keep, noise keywords); no classification-scope
change; no new sources; no weekly briefing; no scheduling.
