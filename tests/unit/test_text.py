"""Unit tests for ai_observatory.collection.text.normalize_summary."""

from __future__ import annotations

import pytest

from ai_observatory.collection.text import normalize_summary


class TestNormalizeSummaryPassthrough:
    def test_plain_text_without_tags_passes_through_unchanged(self) -> None:
        result = normalize_summary("Just plain text.", 500)

        assert result == "Just plain text."

    def test_already_short_text_passes_through_unchanged(self) -> None:
        result = normalize_summary("Short text under limit.", 500)

        assert result == "Short text under limit."

    def test_non_latin_text_passes_through_unchanged(self) -> None:
        raw = "これはテストの要約です。日本語のテキストです。"

        result = normalize_summary(raw, 500)

        assert result == raw


class TestNormalizeSummaryHtml:
    def test_html_entities_are_decoded(self) -> None:
        result = normalize_summary("Tom &amp; Jerry &lt;3", 500)

        assert result == "Tom & Jerry <3"

    def test_broken_and_nested_tags_are_tolerated_without_raising(self) -> None:
        raw = "<p>Nested <b>bold <i>italic</b> broken</i> text</p>"

        result = normalize_summary(raw, 500)

        assert result == "Nested bold italic broken text"


class TestNormalizeSummaryFirstParagraph:
    def test_html_first_paragraph_drops_trailing_tags_via_block(self) -> None:
        raw = (
            "<p>Real summary text here.</p>"
            "<p>Tags: ai, ml</p>"
            "<p>Via: example.com</p>"
        )

        result = normalize_summary(raw, 500)

        assert result == "Real summary text here."

    def test_plain_text_multi_paragraph_body_is_truncated_with_ellipsis(self) -> None:
        raw = (
            "This is a fairly long first paragraph that will definitely "
            "need truncating for the test.\n\n"
            "This second paragraph must never appear anywhere in the output."
        )

        result = normalize_summary(raw, 30)

        assert result.endswith("…")
        assert len(result) <= 30
        assert "second paragraph" not in result


class TestNormalizeSummaryEmptyAndWhitespace:
    def test_whitespace_only_summary_normalizes_to_empty_string(self) -> None:
        result = normalize_summary("   \n\t  ", 500)

        assert result == ""

    def test_zero_max_chars_yields_empty_string(self) -> None:
        result = normalize_summary("Some text that would otherwise pass through.", 0)

        assert result == ""

    def test_negative_max_chars_yields_empty_string(self) -> None:
        result = normalize_summary("Some text that would otherwise pass through.", -1)

        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__])
