# Design: MVP-2 Deterministic Score-Keep Signal Rule

## Technical Approach

Add a third deterministic rule to `synthesis/filter.py::score()`: a per-source
popularity score at/above a configured keep threshold auto-keeps as
`SIGNIFICANT` without an LLM call, mirroring the existing P1 auto-keep.
Collectors (Approach A) own payload knowledge and normalize the native score
into a stable cross-layer contract carried in `Item.raw`: `signal_score` (int)
and `signal_scale` (`"hf_upvotes"` | `"hn_points"`). `score()` stays pure and
source-agnostic — it reads the contract, maps the scale to the matching config
threshold, and auto-keeps. Opt-in and disabled by default: zero behavior change
until a threshold is set. No signature change, no schema change, no new modules.

## Architecture Decisions

### Decision: How `score()` reads the score from `raw`

`Item.raw` is a `str` (JSON string: `json.dumps(entry, default=str)`), persisted
verbatim as a DB column (`storage/db.py:75`). Confirmed the only consumers are
that column write and tests that already do `json.loads(item.raw)`.

| Option | Blast radius | Decision |
|--------|-------------|----------|
| (a) Collectors inject `signal_score`/`signal_scale` into the dict before `json.dumps`; `score()` does defensive `json.loads(item.raw)` | Additive keys only; extra keys harmless to every consumer | **CHOSEN** |
| (b) Change `raw` to a `dict` at source | Touches `Item` model, `db.py` serialization, every collector + test | Rejected — schema/serialization churn |
| (c) Dedicated field/column for score | New `Item` field + migration | Rejected — column is an explicit non-goal |

**Rationale**: (a) is purely additive, matches the existing `json.loads(item.raw)`
test pattern, and keeps `raw` typed as it is today.

### Decision: None-sentinel disables, `0` cannot

Thresholds are `int | None`, default `None`. `0` cannot disable because
`score >= 0` is always true. `None` = disabled short-circuit. Starter values
(HF ~50 / HN ~200) live in prose only, never as defaults.

### Decision: Precedence — score-keep before noise-keyword

A very-high-score item overrides a noise keyword (intended; thresholds set high).

## Data Flow

    HF/HN payload ─► parse_* injects signal_score+signal_scale into raw (JSON str)
                                         │
                              Item.raw ──► score() json.loads (defensive)
                                         │
              scale→threshold map ──► >= keep? ──► SIGNIFICANT / DETERMINISTIC
              (None threshold or bad read) ──► rule doesn't fire ──► fall through

## Precedence Table (inside `score()`)

| # | Rule | Result |
|---|------|--------|
| 1 | `source_priority <= filter_keep_priority` (P1) | `SIGNIFICANT` |
| 2 | score-keep: `signal_score >= <scale threshold>` **[NEW]** | `SIGNIFICANT` |
| 3 | noise keyword in title/summary | `ROUTINE` |
| 4 | none of the above | `None` → LLM |

## Interfaces / Contracts

Additive `raw` contract (namespaced, additive — original keys preserved):
`signal_score: int`, `signal_scale: "hf_upvotes" | "hn_points"`. RSS emits neither.

Collector minimal-diff shape (HF; HN symmetric with `points`/`"hn_points"`):

    raw = json.dumps(
        {**entry, "signal_score": upvotes, "signal_scale": "hf_upvotes"},
        default=str,
    )

New `score()` rule (between P1 and noise-keyword) — defensive pseudocode:

    _SCALE_TO_THRESHOLD = {
        "hf_upvotes": lambda c: c.filter_hf_keep_upvotes,
        "hn_points": lambda c: c.filter_hn_keep_points,
    }
    try:
        raw = json.loads(item.raw)
    except (TypeError, ValueError):
        raw = {}
    scale = raw.get("signal_scale") if isinstance(raw, dict) else None
    score_val = raw.get("signal_score") if isinstance(raw, dict) else None
    selector = _SCALE_TO_THRESHOLD.get(scale)
    if selector is not None and isinstance(score_val, int) and not isinstance(score_val, bool):
        threshold = selector(config)
        if threshold is not None and score_val >= threshold:
            return Verdict.SIGNIFICANT
    # else: rule doesn't fire — fall through to noise-keyword

Guards: malformed/missing raw, non-`dict`, unknown scale, non-int (incl. `bool`)
score, or `None` threshold → rule silently doesn't fire; never raises.

Config helper (mirrors `_int_env`, returns `None` instead of a default):

    def _optional_int_env(name: str) -> int | None:
        raw = os.environ.get(name)
        if raw is None or raw.strip() == "":
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

New fields: `filter_hf_keep_upvotes: int | None` (env `AIOBS_FILTER_HF_KEEP_UPVOTES`),
`filter_hn_keep_points: int | None` (env `AIOBS_FILTER_HN_KEEP_POINTS`), default `None`.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `score()` score-keep: `>=` keeps SIGNIFICANT; below falls through; AT threshold keeps; RSS no-key no-fire; per-source independence; `None` threshold disabled; precedence (noise+high score → SIGNIFICANT); malformed/empty raw no-raise | Hand-built `Item` with signal keys in `raw` + `Config` with/without thresholds — no LLM, no I/O (`tests/unit/test_filter.py`) |
| Unit | `classify_items` score-keep short-circuits LLM (`client.calls == 0`); below-threshold reaches LLM | Fake `LLMClient` (`tests/unit/test_filter.py`) |
| Unit | HF/HN collectors retain `signal_score` (int) + correct `signal_scale`, original keys preserved | Fixtures via `json.loads(item.raw)` (`tests/unit/test_hf_papers.py`, `tests/unit/test_hn_algolia.py`) |
| Unit | `_optional_int_env`: unset/blank → None; valid → int; invalid/negative → None | Env monkeypatch (`tests/unit/test_config.py`) |

Strict TDD: RED first, then `uv run pytest` + `uv run ruff check .`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai_observatory/config.py` | Modify | Add `_optional_int_env`; two `int \| None` fields + env wiring |
| `src/ai_observatory/collection/hf_papers.py` | Modify | Inject `signal_score`/`signal_scale` into `raw` |
| `src/ai_observatory/collection/hn_algolia.py` | Modify | Inject `signal_score`/`signal_scale` into `raw` |
| `src/ai_observatory/synthesis/filter.py` | Modify | New score-keep rule + `json` import + scale→threshold map |
| `src/ai_observatory/storage/models.py` | Modify | `Item.raw` docstring: note additive `signal_score`/`signal_scale` keys |
| `tests/unit/test_filter.py` | Modify | Score-keep + precedence + defensive tests |
| `tests/unit/test_hf_papers.py` | Modify | Assert new raw keys |
| `tests/unit/test_hn_algolia.py` | Modify | Assert new raw keys |
| `tests/unit/test_config.py` | Modify | `_optional_int_env` + new fields |

No new modules. `Item.raw` stays `str`.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. Pure functions + config only.

## Migration / Rollout

No migration required. Additive, opt-in. Both thresholds `None` (default) →
rule never fires → behavior identical to today even without revert. Raw keys
harmless if unread. Rollback = revert branch.

## Open Questions

None — all four proposal decisions are LOCKED.
