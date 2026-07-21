"""Typer CLI: the `collect` command wiring the full collection pipeline."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import typer

from ai_observatory.collection.dedup import dedup_batch
from ai_observatory.collection.rss import HttpxFetcher, RssCollector
from ai_observatory.collection.sources import load_sources
from ai_observatory.config import Config
from ai_observatory.storage import db, records

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.callback()
def callback() -> None:
    """AI Observatory: local-first AI news collection."""


@app.command()
def collect() -> None:
    """Fetch, dedup, store, and render daily records for all configured sources."""
    config = Config.from_env()
    sources = load_sources(config.sources_path)

    fetcher = HttpxFetcher(user_agent=config.user_agent)
    collector = RssCollector(fetcher)

    collected_items = []
    for source in sources:
        collected_items.extend(collector.collect(source))

    deduped_items = dedup_batch(collected_items)

    connection = db.connect(config.db_path)
    try:
        db.upsert_items(connection, deduped_items)

        affected_dates = {item.published_at.date() for item in deduped_items}
        affected_dates.add(datetime.now(UTC).date())

        for target_date in affected_dates:
            day_items = db.items_for_date(connection, target_date)
            content = records.render_markdown(day_items, target_date)
            record_path = Path(config.records_dir) / f"{target_date.isoformat()}.md"
            records.write_record(record_path, content)
    finally:
        connection.close()
