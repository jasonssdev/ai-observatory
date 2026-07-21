"""Hybrid significance classifier: deterministic rules + LLM fallback.

Deterministic rules decide the obvious cases without I/O; the injected
`LLMClient` port decides only the UNCERTAIN remainder. The whole run
degrades to deterministic-only (never fails) on the first `LLMError`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from ai_observatory.config import Config
from ai_observatory.storage.models import Item
from ai_observatory.synthesis.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)

NOISE_KEYWORDS = [
    "funding round",
    "hiring",
    "webinar",
    "sponsored",
]


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


def score(item: Item, config: Config) -> Verdict | None:
    """Classify `item` deterministically, or return `None` if UNCERTAIN.

    High-priority sources (`source_priority <= config.filter_keep_priority`)
    are auto-kept as `SIGNIFICANT`. Items whose title or summary match a
    configured noise keyword are auto-dropped as `ROUTINE`. Anything else
    is UNCERTAIN (`None`) and left for the LLM to decide.
    """
    if item.source_priority <= config.filter_keep_priority:
        return Verdict.SIGNIFICANT

    haystack = f"{item.title} {item.summary}".lower()
    if any(keyword in haystack for keyword in NOISE_KEYWORDS):
        return Verdict.ROUTINE

    return None


def parse_verdict(text: str) -> Verdict:
    """Tolerantly parse an LLM verdict string, defaulting to `ROUTINE`.

    Normalizes case/whitespace and matches by substring. An unparseable
    or ambiguous response defaults to `ROUTINE` (the documented safe
    default — never `SIGNIFICANT` by default).
    """
    normalized = text.strip().lower()
    if "significant" in normalized:
        return Verdict.SIGNIFICANT
    return Verdict.ROUTINE


def build_prompt(item: Item) -> str:
    """Build the one-word-verdict classification prompt for `item`."""
    return (
        "You are classifying a news item as SIGNIFICANT or ROUTINE for a "
        "daily AI news digest. Respond with exactly one word: SIGNIFICANT "
        "or ROUTINE.\n\n"
        f"Title: {item.title}\n"
        f"Summary: {item.summary}\n\n"
        "Verdict:"
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
