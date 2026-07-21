"""Pure summary normalization: HTML stripping, first-paragraph, truncation."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_ELLIPSIS = "…"
_CLOSING_P_TAG = re.compile(r"</p>", re.IGNORECASE)
_BLANK_LINE = re.compile(r"\r?\n\s*\r?\n")
_WHITESPACE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    """Tolerant HTML tag stripper: collects text data, decodes entities once.

    `convert_charrefs=True` decodes character references inline before they
    reach `handle_data`. Broken/nested tags are tokenized sequentially by
    the stdlib parser (no tree-balancing required), so malformed markup
    never raises here.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def _strip_tags(text: str) -> str:
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return parser.get_text()


def _first_paragraph(raw_summary: str) -> str:
    """Extract the first paragraph from the raw (pre-tag-stripping) string.

    Prefers the first `</p>` (case-insensitive) when HTML is present;
    otherwise falls back to the text before the first blank line; else the
    whole string is treated as a single paragraph.
    """
    closing_p = _CLOSING_P_TAG.search(raw_summary)
    if closing_p:
        return raw_summary[: closing_p.end()]

    blank_line = _BLANK_LINE.search(raw_summary)
    if blank_line:
        return raw_summary[: blank_line.start()]

    return raw_summary


def normalize_summary(raw_summary: str, max_chars: int) -> str:
    """Normalize a raw feed summary into short, clean plain text.

    Order: guard non-positive `max_chars`; extract the first paragraph from
    the raw string; strip HTML tags and decode entities; collapse
    whitespace; then truncate with an ellipsis so the total rendered
    length (including the ellipsis) never exceeds `max_chars`.
    """
    if max_chars <= 0:
        return ""

    paragraph = _first_paragraph(raw_summary)
    text = _strip_tags(paragraph)
    text = _WHITESPACE.sub(" ", text).strip()

    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars < len(_ELLIPSIS):
        return ""

    keep = max_chars - len(_ELLIPSIS)
    return text[:keep].rstrip() + _ELLIPSIS
