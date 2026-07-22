# Design: MVP-2 Deterministic Routine for Research/arXiv Categories

## Technical Approach

Add a fourth deterministic rule to `synthesis/filter.py::score()`: an item whose
normalized `category` is in a configured routine-category set is classified
`ROUTINE` without an LLM call. It sits AFTER both SIGNIFICANT auto-keep tiers
(P1 priority, score-keep) and BEFORE the noise-keyword rule, so genuinely
high-priority (HF Daily Papers, P1) and high-score research still stay
SIGNIFICANT while individual P2 arXiv/research papers are set aside pre-LLM.
The discriminator is the already-modeled `Item.category` (fixed `sources.yaml`
vocabulary: lab, research, newsletter, news, tooling, community) — no string
parsing of display names, no schema/`sources.yaml` change. Config mirrors the
proven score-keep opt-in shape but with a NON-empty default. `score()` stays
pure and keeps its signature; no new modules.

## Architecture Decisions

### Decision: `category`-based discriminator, not source names

| Option | Blast radius | Decision |
|--------|--------------|----------|
| (a) Match `item.category` against a normalized set | Reads an existing field; additive | **CHOSEN** |
| (b) Match source display names / substrings | Brittle; breaks on rename | Rejected |
| (c) New `Item` field/column or `sources.yaml` change | Schema churn (non-goal) | Rejected |

**Rationale**: `category` is persisted, sourced from a fixed vocabulary, and
uniquely identifies research/arXiv without brittle matching.

### Decision: Default ON = `frozenset({"research"})` (user-confirmed)

Unlike the score-keep precedent (default OFF), this rule defaults ON to fix the
arXiv-as-signal leak out of the box (roadmap "suppress the routine" bar).
Tradeoff acknowledged and confirmed: default-ON CHANGES upgrade behavior and
routes Google Research (P2, `category=research`) to ROUTINE. Reversible with one
env var (`AIOBS_FILTER_ROUTINE_CATEGORIES=`).

### Decision: Empty set disables; unset applies the default

The parse helper takes a `default` applied ONLY when the env var is **unset**
(`os.environ.get is None`). A **present** value (including `""`, whitespace, or
commas only) parses to a possibly-empty frozenset — an empty set disables the
rule. This differs from `_optional_int_env` (which returns `None` for both
unset and blank) precisely because default-ON needs unset ≠ blank.

### Decision: Precedence — category-routine after both auto-keeps, before noise

Placing it after score-keep guarantees a raised `filter_keep_priority` (P2
auto-keep) and any high-score research still win SIGNIFICANT before this rule.

### Decision: Shared normalization contract, not a cross-module helper

Both config-token parsing and the `score()` compare use `.strip().casefold()`.
The vocabulary is already lowercase, so a single documented normalization
contract is enough; a cross-module shared function would add import coupling
for no behavioral gain. `filter.py` keeps a private `_normalize_category`.

## Precedence Table (inside `score()`)

| # | Rule | Result |
|---|------|--------|
| 1 | `source_priority <= filter_keep_priority` (P1) | `SIGNIFICANT` |
| 2 | score-keep: `signal_score >= threshold` | `SIGNIFICANT` |
| 3 | category-routine: `norm(category) in set` **[NEW]** | `ROUTINE` |
| 4 | noise keyword in title/summary | `ROUTINE` |
| 5 | none of the above | `None` → LLM |

## Data Flow

    Item.category ─► _normalize_category (strip+casefold)
                              │
        config.filter_routine_categories (normalized frozenset)
                              │
         in set? ──► ROUTINE / DETERMINISTIC (no LLM call)
         empty set / not in set / blank ──► fall through to noise-keyword/LLM

## Interfaces / Contracts

Config helper (mirrors `_int_env`; default applies only when unset):

    def _frozenset_env(name: str, default: frozenset[str]) -> frozenset[str]:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return frozenset(
            token.strip().casefold()
            for token in raw.split(",")
            if token.strip()
        )

New field: `filter_routine_categories: frozenset[str]`, env
`AIOBS_FILTER_ROUTINE_CATEGORIES`, default `frozenset({"research"})`.

New `score()` rule (between score-keep and noise-keyword):

    if item.category and _normalize_category(item.category) in config.filter_routine_categories:
        return Verdict.ROUTINE

Guard: empty config set → never fires; missing/blank/unknown category →
`_normalize_category` yields a value not in the set → falls through. Never raises.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/config.py` | Modify | Add `_frozenset_env`; `filter_routine_categories` field + env wiring + default |
| `src/ai_observatory/synthesis/filter.py` | Modify | Add `_normalize_category` + category-routine rule after score-keep |
| `tests/unit/test_config.py` | Modify | `_frozenset_env` + field (unset→default, blank→empty, parsed/normalized) |
| `tests/unit/test_filter.py` | Modify | Rule, precedence, LLM short-circuit, defensive; `_config` gains field |
| `openspec/specs/hybrid-filter/spec.md` | Modify (sdd-spec) | New requirement + config extension |

No new modules. No `Item`/schema change. `score()` signature unchanged.

## Testing Strategy

| Layer | What to test | Approach |
|-------|--------------|----------|
| Unit (config) | `_frozenset_env`: unset→default; blank/commas-only→empty; `"research"`→`{"research"}`; `"Research, ML "`→`{"research","ml"}` (casefold+strip, empties dropped). Field: `Config.from_env` default `{"research"}`; override parsed; `AIOBS_FILTER_ROUTINE_CATEGORIES=`→empty (disabled) | Env monkeypatch (`test_config.py`) |
| Unit (rule) | research item → `score()` == ROUTINE; non-research (news/tooling) → falls through (`None`); empty set → research item falls through; defensive: unknown/blank category no-raise, no-fire | Hand-built `Item` + `_config(filter_routine_categories=...)` (`test_filter.py`) |
| Unit (precedence) | P1 research stays SIGNIFICANT; high-score research stays SIGNIFICANT; raised `filter_keep_priority=2` → P2 research auto-kept SIGNIFICANT before routine rule | `_config` variants (`test_filter.py`) |
| Unit (short-circuit) | `classify_items` on a research item → `client.calls == 0`; non-research reaches LLM | Fake `LLMClient` (`test_filter.py`) |

`_config` helper in `test_filter.py` gains a `filter_routine_categories:
frozenset[str] = frozenset()` kwarg so existing tests default to the rule
disabled (no behavior drift) and new tests opt in explicitly.

Strict TDD: RED first, then `uv run pytest` + `uv run ruff check .`.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. Pure function + config only.

## Migration / Rollout

No migration. Default-ON is an intended, documented behavior change on upgrade;
`data/` is gitignored and past records are untouched (rule runs at
classification time). Rollback without code revert: set
`AIOBS_FILTER_ROUTINE_CATEGORIES=` (empty) to restore today's LLM path.

## Open Questions

None — the default-ON `{"research"}` policy is user-confirmed; all decisions LOCKED.
