"""Typer CLI: the `collect` command wiring the full collection pipeline."""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import typer

from ai_observatory.collection.base import Collector
from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.hf_papers import HfPapersCollector
from ai_observatory.collection.hn_algolia import HnAlgoliaCollector
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


def _configure_logging() -> None:
    """Enable app-wide INFO logging while silencing httpx/httpcore noise.

    `httpx`/`httpcore` emit an INFO-level line per HTTP request, which
    would otherwise bury the app's own logging and the end-of-run summary.
    Raising just those two loggers to WARNING keeps app INFO/warnings and
    the summary visible.
    """
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@app.command()
def collect() -> None:
    """Fetch, dedup, store, and render daily records for all configured sources."""
    _configure_logging()

    config = Config.from_env()
    sources = load_sources(config.sources_path)

    fetcher = HttpxFetcher(user_agent=config.user_agent)
    collectors: dict[str, Collector] = {
        "rss": RssCollector(fetcher, config.summary_max_chars),
        "hf_papers": HfPapersCollector(
            fetcher, config.summary_max_chars, config.hf_min_upvotes
        ),
        "hn_algolia": HnAlgoliaCollector(
            fetcher, config.summary_max_chars, config.hn_min_points
        ),
    }

    collected_items = []
    sources_queried = 0
    empty_sources = 0
    for source in sources:
        collector = collectors.get(source.collector)
        if collector is None:
            logger.warning(
                "Skipping source %s: unknown collector %r",
                source.name,
                source.collector,
            )
            continue
        sources_queried += 1
        items = collector.collect(source)
        if not items:
            empty_sources += 1
            logger.warning("Source %s returned no items", source.name)
        collected_items.extend(items)

    deduped_items = dedup_batch(collected_items)

    connection = db.connect(config.db_path)
    try:
        db.upsert_items(connection, deduped_items)

        today = datetime.now(UTC).date()
        start = records.window_start(today, config.record_window_days)
        end = today + timedelta(days=1)

        llm_client = OllamaClient(
            config.ollama_url, config.ollama_model, config.ollama_timeout_seconds
        )
        unclassified = db.unclassified_within(connection, start, end)
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

        classified_count = len(verdicts)
        significant_count = sum(
            verdict.label == Verdict.SIGNIFICANT for verdict in verdicts
        )
        set_aside_count = classified_count - significant_count
        typer.echo(f"Sources queried: {sources_queried}")
        typer.echo(f"Sources returning nothing: {empty_sources}")
        typer.echo(f"Items collected: {len(collected_items)}")
        typer.echo(f"Items after dedup: {len(deduped_items)}")
        typer.echo(
            f"Items classified this run: {classified_count} "
            f"(significant: {significant_count}, set aside: {set_aside_count})"
        )
        typer.echo(f"Filter mode: {mode}")
    finally:
        connection.close()
