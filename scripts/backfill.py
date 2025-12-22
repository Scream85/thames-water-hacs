#!/usr/bin/env python3
"""Backfill water usage data using the scraper."""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_database
from src.database.models import SyncLog
from src.database.queries import insert_daily_usage, insert_hourly_usage, create_sync_log
from src.scraper.extractor import ThamesWaterExtractor
from src.scheduler.jobs import check_for_spike
from src.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def backfill(months: list[str] | None = None) -> None:
    """
    Backfill data using the scraper.

    Args:
        months: Optional list of months to fetch (e.g., ['Dec-2025', 'Nov-2025'])
                If not provided, fetches all available months.
    """
    logger.info(f"Starting backfill for months: {months or 'all available'}")

    # Connect to database
    db = get_database()
    await db.connect()

    sync_log = SyncLog(
        sync_type='backfill',
        sync_time=datetime.now(timezone.utc),
        status='success',
    )

    try:
        extractor = ThamesWaterExtractor()

        if months:
            daily_records, hourly_records = extractor.run(months=months, include_hourly=True)
        else:
            # Fetch all available months
            daily_records, hourly_records = extractor.run(include_hourly=True)

        daily_stored = 0
        for record in daily_records:
            await insert_daily_usage(record)
            daily_stored += 1

            # Check for spikes
            await check_for_spike(record)

        hourly_stored = 0
        for record in hourly_records:
            await insert_hourly_usage(record)
            hourly_stored += 1

        sync_log.records_fetched = len(daily_records) + len(hourly_records)
        sync_log.records_stored = daily_stored + hourly_stored

        if daily_records:
            dates = [r.date for r in daily_records]
            sync_log.date_range_start = min(dates)
            sync_log.date_range_end = max(dates)

        logger.info(f"Backfill complete: {daily_stored} daily + {hourly_stored} hourly records stored")

    except Exception as e:
        sync_log.status = 'error'
        sync_log.error_message = str(e)
        logger.error(f"Backfill failed: {e}")
        raise

    finally:
        await create_sync_log(sync_log)
        await db.disconnect()


def main():
    """Main entry point."""
    # Default months to backfill (December 2025)
    months = ['Dec-2025']

    if len(sys.argv) > 1:
        # Parse months from command line
        months = sys.argv[1:]

    asyncio.run(backfill(months))


if __name__ == "__main__":
    main()
