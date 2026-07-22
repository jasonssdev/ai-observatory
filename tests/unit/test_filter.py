"""Unit tests for ai_observatory.synthesis.filter: hybrid significance classifier."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ai_observatory.config import Config
from ai_observatory.storage.models import Item
from ai_observatory.synthesis.filter import (
    Mode,
    Significance,
    Verdict,
    build_prompt,
    classify_items,
    parse_verdict,
    score,
)
from ai_observatory.synthesis.llm import LLMError, LLMResponse


def _config(
    *,
    filter_keep_priority: int = 1,
    filter_hf_keep_upvotes: int | None = None,
    filter_hn_keep_points: int | None = None,
) -> Config:
    return Config(
        data_dir="./data",
        db_path="data/observatory.db",
        records_dir="data/records",
        sources_path="./sources.yaml",
        user_agent="test-agent",
        record_window_days=7,
        summary_max_chars=500,
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2",
        ollama_timeout_seconds=60.0,
        filter_keep_priority=filter_keep_priority,
        hf_min_upvotes=5,
        hn_min_points=30,
        filter_hf_keep_upvotes=filter_hf_keep_upvotes,
        filter_hn_keep_points=filter_hn_keep_points,
    )


def _item(
    *,
    id_: str = "a",
    title: str = "A neutral headline",
    summary: str = "A neutral summary.",
    source_priority: int = 2,
    raw: str = "{}",
) -> Item:
    return Item(
        id=id_,
        title=title,
        url="https://example.com/a",
        source="Source",
        source_priority=source_priority,
        category="lab",
        published_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        collected_at=datetime(2026, 7, 20, 12, 0, tzinfo=UTC),
        summary=summary,
        raw=raw,
    )


class TestScoreAutoKeep:
    def test_source_priority_at_or_below_threshold_is_significant(self) -> None:
        item = _item(source_priority=1)

        assert score(item, _config(filter_keep_priority=1)) == Verdict.SIGNIFICANT

    def test_source_priority_above_threshold_is_not_auto_kept(self) -> None:
        item = _item(source_priority=3, title="Neutral", summary="Neutral")

        assert score(item, _config(filter_keep_priority=1)) is None


class TestScoreNoiseKeywordDrop:
    def test_title_matching_noise_keyword_is_routine(self) -> None:
        item = _item(source_priority=5, title="Funding round announced", summary="")

        assert score(item, _config(filter_keep_priority=1)) == Verdict.ROUTINE

    def test_summary_matching_noise_keyword_is_routine(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral headline",
            summary="This company closed a funding round today.",
        )

        assert score(item, _config(filter_keep_priority=1)) == Verdict.ROUTINE


def _raw(signal_score: object, signal_scale: object) -> str:
    return json.dumps({"signal_score": signal_score, "signal_scale": signal_scale})


class TestScoreKeepRule:
    def test_score_at_or_above_threshold_is_significant(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(50, "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=50))

        assert verdict == Verdict.SIGNIFICANT

    def test_score_keep_precedes_noise_keyword(self) -> None:
        item = _item(
            source_priority=5,
            title="Funding round announced",
            summary="",
            raw=_raw(50, "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=50))

        assert verdict == Verdict.SIGNIFICANT

    def test_score_below_threshold_falls_through(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(10, "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=50))

        assert verdict is None

    def test_threshold_none_never_fires(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(9999, "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=None))

        assert verdict is None

    def test_no_signal_keys_does_not_fire(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw="{}",
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=1))

        assert verdict is None

    def test_hf_and_hn_thresholds_are_independent(self) -> None:
        hf_item = _item(
            id_="hf",
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(50, "hf_upvotes"),
        )
        hn_item = _item(
            id_="hn",
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(200, "hn_points"),
        )
        config = _config(filter_hf_keep_upvotes=50, filter_hn_keep_points=None)

        assert score(hf_item, config) == Verdict.SIGNIFICANT
        assert score(hn_item, config) is None

    def test_malformed_raw_does_not_raise(self) -> None:
        item = _item(
            source_priority=5, title="Neutral", summary="Neutral", raw="not json"
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=1))

        assert verdict is None

    def test_non_int_signal_score_does_not_fire(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw("fifty", "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=1))

        assert verdict is None

    def test_bool_signal_score_does_not_fire(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(True, "hf_upvotes"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=0))

        assert verdict is None

    def test_unknown_signal_scale_does_not_fire(self) -> None:
        item = _item(
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(9999, "unknown_scale"),
        )

        verdict = score(item, _config(filter_hf_keep_upvotes=1))

        assert verdict is None


class TestClassifyItemsScoreKeep:
    def test_score_keep_verdict_never_reaches_llm(self) -> None:
        item = _item(
            id_="score-keep",
            source_priority=5,
            title="Neutral",
            summary="Neutral",
            raw=_raw(50, "hf_upvotes"),
        )
        client = _FakeLLMClient([])

        verdicts, llm_available = classify_items(
            [item], client, _config(filter_hf_keep_upvotes=50)
        )

        assert verdicts == [
            Significance(
                item_id="score-keep",
                label=Verdict.SIGNIFICANT,
                mode=Mode.DETERMINISTIC,
                model=None,
            )
        ]
        assert llm_available is True
        assert client.calls == 0


class TestScoreUncertain:
    def test_neither_rule_matches_returns_none(self) -> None:
        item = _item(
            source_priority=5,
            title="A neutral technical headline",
            summary="A neutral technical summary.",
        )

        assert score(item, _config(filter_keep_priority=1)) is None


class TestParseVerdict:
    def test_significant_case_and_whitespace_tolerant(self) -> None:
        assert parse_verdict("  Significant  ") == Verdict.SIGNIFICANT

    def test_routine_case_and_whitespace_tolerant(self) -> None:
        assert parse_verdict("  ROUTINE\n") == Verdict.ROUTINE

    def test_substring_match_within_longer_sentence(self) -> None:
        assert parse_verdict("Verdict: SIGNIFICANT.") == Verdict.SIGNIFICANT

    def test_leading_word_with_trailing_text(self) -> None:
        assert (
            parse_verdict("SIGNIFICANT — major model release") == Verdict.SIGNIFICANT
        )


class TestParseVerdictNegation:
    def test_negated_significant_is_routine(self) -> None:
        assert (
            parse_verdict("This is not significant, it's routine.")
            == Verdict.ROUTINE
        )

    def test_insignificant_is_not_a_significant_token(self) -> None:
        assert parse_verdict("insignificant") == Verdict.ROUTINE


class TestParseVerdictMalformedDefault:
    def test_unparseable_text_defaults_to_routine(self) -> None:
        assert parse_verdict("I cannot decide.") == Verdict.ROUTINE

    def test_empty_string_defaults_to_routine(self) -> None:
        assert parse_verdict("") == Verdict.ROUTINE


class TestBuildPrompt:
    def test_prompt_contains_title_summary_and_instruction(self) -> None:
        item = _item(title="Breaking AI News", summary="Something happened.")

        prompt = build_prompt(item)

        assert "Breaking AI News" in prompt
        assert "Something happened." in prompt
        assert "SIGNIFICANT" in prompt
        assert "ROUTINE" in prompt

    def test_prompt_contains_rubric_and_one_word_instruction(self) -> None:
        item = _item(title="Breaking AI News", summary="Something happened.")

        prompt = build_prompt(item)

        assert "breakthrough" in prompt
        assert "tutorials" in prompt
        assert "roundups" in prompt
        assert "Answer with ONLY one word" in prompt


class _FakeLLMClient:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMResponse(text=response, model="llama3.2", raw={})


class TestClassifyItemsLLM:
    def test_llm_significant_verdict_is_recorded_with_model(self) -> None:
        item = _item(id_="uncertain", source_priority=5, title="Neutral", summary="")
        client = _FakeLLMClient(["SIGNIFICANT"])

        verdicts, llm_available = classify_items(
            [item], client, _config(filter_keep_priority=1)
        )

        assert verdicts == [
            Significance(
                item_id="uncertain",
                label=Verdict.SIGNIFICANT,
                mode=Mode.LLM,
                model="llama3.2",
            )
        ]
        assert llm_available is True

    def test_llm_routine_verdict_is_recorded(self) -> None:
        item = _item(id_="uncertain", source_priority=5, title="Neutral", summary="")
        client = _FakeLLMClient(["ROUTINE"])

        verdicts, _llm_available = classify_items(
            [item], client, _config(filter_keep_priority=1)
        )

        assert verdicts[0].label == Verdict.ROUTINE
        assert verdicts[0].mode == Mode.LLM


class TestClassifyItemsMalformedOutput:
    def test_malformed_llm_text_defaults_to_routine_but_mode_stays_llm(self) -> None:
        item = _item(id_="uncertain", source_priority=5, title="Neutral", summary="")
        client = _FakeLLMClient(["not a real answer"])

        verdicts, _llm_available = classify_items(
            [item], client, _config(filter_keep_priority=1)
        )

        assert verdicts[0].label == Verdict.ROUTINE
        assert verdicts[0].mode == Mode.LLM


class TestClassifyItemsRunLevelFallback:
    def test_first_llm_error_degrades_whole_run(self) -> None:
        items = [
            _item(id_="one", source_priority=5, title="Neutral 1", summary=""),
            _item(id_="two", source_priority=5, title="Neutral 2", summary=""),
            _item(id_="three", source_priority=5, title="Neutral 3", summary=""),
        ]
        client = _FakeLLMClient([LLMError("server down")])

        verdicts, llm_available = classify_items(
            items, client, _config(filter_keep_priority=1)
        )

        assert llm_available is False
        assert client.calls == 1
        assert [v.label for v in verdicts] == [
            Verdict.ROUTINE,
            Verdict.ROUTINE,
            Verdict.ROUTINE,
        ]
        assert [v.mode for v in verdicts] == [
            Mode.DETERMINISTIC,
            Mode.DETERMINISTIC,
            Mode.DETERMINISTIC,
        ]


class TestClassifyItemsPure:
    def test_returns_plain_lists_with_no_storage_import(self) -> None:
        import ai_observatory.synthesis.filter as filter_module

        assert "ai_observatory.storage.db" not in dir(filter_module)

        item = _item(id_="a", source_priority=1)
        client = _FakeLLMClient([])

        verdicts, llm_available = classify_items(
            [item], client, _config(filter_keep_priority=1)
        )

        assert isinstance(verdicts, list)
        assert llm_available is True
        assert client.calls == 0  # P1 item never reaches the LLM


if __name__ == "__main__":
    pytest.main([__file__])
