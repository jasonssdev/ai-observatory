"""Typer CLI: the `collect` command wiring the full collection pipeline."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.rss import HttpxFetcher, RssCollector
from ai_observatory.collection.sources import load_sources
from ai_observatory.config import Config
from ai_observatory.storage import db, records
from ai_observatory.synthesis.filter import Verdict, classify_items
from ai_observatory.synthesis.llm import OllamaClient

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.callback()
def callback() -> None:
    """AI Observatory: local-first AI news collection."""


def _write_daily_records(
    connection: sqlite3.Connection,
    records_dir: Path | str,
    candidate_dates: set[date],
    today: date,
    window_days: int,
    mode: str,
) -> None:
    """Render and write Markdown records for dates within the recent window.

    Filters `candidate_dates` down to those within `window_days` of `today`
    (always including `today`), then regenerates one Markdown file per kept
    date from the current DB contents. Each day's items are split into
    significant/set-aside buckets from persisted significance verdicts.
    Classification only ever runs for `today`, so historical in-window days
    can have items with no verdict yet — those default to `ROUTINE`
    (set-aside) rather than crashing or silently disappearing.
    """
    kept_dates = records.dates_within_window(candidate_dates, today, window_days)
    for target_date in kept_dates:
        day_items = db.items_for_date(connection, target_date)
        verdicts = {
            verdict.item_id: verdict.label
            for verdict in db.significance_for_date(connection, target_date)
        }
        significant_ids = {
            item.id
            for item in day_items
            if verdicts.get(item.id, Verdict.ROUTINE) == Verdict.SIGNIFICANT
        }
        significant = [item for item in day_items if item.id in significant_ids]
        set_aside = [item for item in day_items if item.id not in significant_ids]
        content = records.render_markdown(significant, set_aside, target_date, mode)
        record_path = Path(records_dir) / f"{target_date.isoformat()}.md"
        records.write_record(record_path, content)


@app.command()
def collect() -> None:
    """Fetch, dedup, store, and render daily records for all configured sources."""
    config = Config.from_env()
    sources = load_sources(config.sources_path)

    fetcher = HttpxFetcher(user_agent=config.user_agent)
    collector = RssCollector(fetcher, config.summary_max_chars)

    collected_items = []
    for source in sources:
        collected_items.extend(collector.collect(source))

    deduped_items = dedup_batch(collected_items)

    connection = db.connect(config.db_path)
    try:
        db.upsert_items(connection, deduped_items)

        today = datetime.now(UTC).date()

        llm_client = OllamaClient(
            config.ollama_url, config.ollama_model, config.ollama_timeout_seconds
        )
        unclassified = db.unclassified_for_date(connection, today)
        verdicts, llm_available = classify_items(unclassified, llm_client, config)
        db.upsert_significance(connection, verdicts)
        mode = "hybrid" if llm_available else "deterministic-only"

        candidate_dates = {item.published_at.date() for item in deduped_items}
        candidate_dates.add(today)

        _write_daily_records(
            connection,
            config.records_dir,
            candidate_dates,
            today,
            config.record_window_days,
            mode,
        )
    finally:
        connection.close()
