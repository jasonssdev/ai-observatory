"""Hybrid significance classifier: deterministic rules + LLM fallback.

Deterministic rules decide the obvious cases without I/O; the injected
`LLMClient` port decides only the UNCERTAIN remainder. The whole run
degrades to deterministic-only (never fails) on the first `LLMError`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum

from ai_observatory.config import Config
from ai_observatory.storage.models import (
    SIGNAL_SCALE_KEY,
    SIGNAL_SCORE_KEY,
    Item,
    SignalScale,
)
from ai_observatory.synthesis.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)

NOISE_KEYWORDS = [
    "funding round",
    "hiring",
    "webinar",
    "sponsored",
]

# Maps a collector's `raw[SIGNAL_SCALE_KEY]` tag to the `Config` field
# holding its keep threshold. `None` threshold means the rule is disabled
# for that scale.
_SCALE_TO_THRESHOLD = {
    SignalScale.HF_UPVOTES: lambda config: config.filter_hf_keep_upvotes,
    SignalScale.HN_POINTS: lambda config: config.filter_hn_keep_points,
}


class Verdict(StrEnum):
    """A significance classification outcome."""

    SIGNIFICANT = "SIGNIFICANT"
    ROUTINE = "ROUTINE"


class Mode(StrEnum):
    """How a `Verdict` was produced."""

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"


@dataclass(frozen=True)
class Significance:
    """A persisted-shape classification result for one item."""

    item_id: str
    label: Verdict
    mode: Mode
    model: str | None


def _meets_score_keep_threshold(item: Item, config: Config) -> bool:
    """Check `item`'s normalized popularity score against its keep threshold.

    Never raises: malformed `raw`, a non-dict payload, a missing/non-int
    (bools excluded) `signal_score`, an unrecognized `signal_scale`, or a
    disabled (`None`) threshold all simply mean the rule does not fire.
    """
    try:
        raw = json.loads(item.raw)
    except (TypeError, ValueError):
        return False

    if not isinstance(raw, dict):
        return False

    scale = raw.get(SIGNAL_SCALE_KEY)
    score_value = raw.get(SIGNAL_SCORE_KEY)
    threshold_selector = _SCALE_TO_THRESHOLD.get(scale)
    if threshold_selector is None:
        return False

    if not isinstance(score_value, int) or isinstance(score_value, bool):
        return False

    threshold = threshold_selector(config)
    if threshold is None:
        return False

    return score_value >= threshold


def score(item: Item, config: Config) -> Verdict | None:
    """Classify `item` deterministically, or return `None` if UNCERTAIN.

    High-priority sources (`source_priority <= config.filter_keep_priority`)
    are auto-kept as `SIGNIFICANT`. Items whose normalized
    `raw[SIGNAL_SCORE_KEY]` meets or exceeds the per-`raw[SIGNAL_SCALE_KEY]`
    keep threshold are also auto-kept as `SIGNIFICANT` (this rule is
    evaluated before the noise-keyword rule, so a high score overrides a
    noise keyword). Items whose
    title or summary match a configured noise keyword are auto-dropped as
    `ROUTINE`. Anything else is UNCERTAIN (`None`) and left for the LLM to
    decide.
    """
    if item.source_priority <= config.filter_keep_priority:
        return Verdict.SIGNIFICANT

    if _meets_score_keep_threshold(item, config):
        return Verdict.SIGNIFICANT

    haystack = f"{item.title} {item.summary}".lower()
    if any(keyword in haystack for keyword in NOISE_KEYWORDS):
        return Verdict.ROUTINE

    return None


_NEGATIONS = {"not", "no", "non", "isn't", "isnt"}


def parse_verdict(text: str) -> Verdict:
    """Tolerantly parse an LLM verdict string, defaulting to `ROUTINE`.

    Normalizes case/whitespace and matches by word-boundary token, not
    substring — so `"insignificant"` never resolves as `"significant"`.
    Scans tokens left-to-right for the first decisive word
    (`"significant"` or `"routine"`). A `"significant"` token immediately
    preceded by a negation word (`not`, `no`, `non`, `isn't`, `isnt`)
    resolves to `ROUTINE`. An unparseable, empty, or ambiguous response
    (no decisive token found) defaults to `ROUTINE` (the documented safe
    default — never `SIGNIFICANT` by default). Pure, never raises.
    """
    tokens = re.findall(r"[a-z']+", text.lower())
    for i, token in enumerate(tokens):
        if token == "significant":
            if i > 0 and tokens[i - 1] in _NEGATIONS:
                return Verdict.ROUTINE
            return Verdict.SIGNIFICANT
        if token == "routine":
            return Verdict.ROUTINE
    return Verdict.ROUTINE


def build_prompt(item: Item) -> str:
    """Build the one-word-verdict classification prompt for `item`.

    Includes a compact significance rubric so the LLM has concrete
    criteria instead of guessing. Wording is operator-tunable and not a
    fixed contract.
    """
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


def classify_items(
    items: list[Item], llm_client: LLMClient, config: Config
) -> tuple[list[Significance], bool]:
    """Classify every item, deterministic-first, LLM for the UNCERTAIN rest.

    Pure with respect to storage: takes and returns plain lists, performs
    no database I/O. On the first `LLMError` raised by `llm_client`, the
    whole run degrades to deterministic-only: the failing item and every
    subsequent UNCERTAIN item are classified `ROUTINE`/`DETERMINISTIC`
    without further LLM calls. The run never raises.

    Returns `(verdicts, llm_available)` where `llm_available` is `False`
    once the run has degraded.
    """
    llm_available = True
    verdicts: list[Significance] = []

    for item in items:
        deterministic_verdict = score(item, config)
        if deterministic_verdict is not None:
            verdicts.append(
                Significance(
                    item_id=item.id,
                    label=deterministic_verdict,
                    mode=Mode.DETERMINISTIC,
                    model=None,
                )
            )
            continue

        if not llm_available:
            verdicts.append(
                Significance(
                    item_id=item.id,
                    label=Verdict.ROUTINE,
                    mode=Mode.DETERMINISTIC,
                    model=None,
                )
            )
            continue

        try:
            response = llm_client.generate(build_prompt(item))
        except LLMError:
            logger.warning(
                "LLM unavailable; run degraded to deterministic-only"
            )
            llm_available = False
            verdicts.append(
                Significance(
                    item_id=item.id,
                    label=Verdict.ROUTINE,
                    mode=Mode.DETERMINISTIC,
                    model=None,
                )
            )
            continue

        verdicts.append(
            Significance(
                item_id=item.id,
                label=parse_verdict(response.text),
                mode=Mode.LLM,
                model=response.model,
            )
        )

    return verdicts, llm_available
