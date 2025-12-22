#!/usr/bin/env python3
"""Test hourly data extraction."""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_database
from src.database.queries import insert_hourly_usage, get_hourly_usage
from src.scraper.extractor import ThamesWaterExtractor
from src.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def test_hourly_extraction() -> None:
    """Test hourly data extraction with correct date range."""
    logger.info("Starting hourly extraction test")

    # Connect to database
    db = get_database()
    await db.connect()

    try:
        extractor = ThamesWaterExtractor()

        # This will now extract for the correct date range (7 days with 3-day delay)
        hourly_records = extractor.run(include_hourly=True, months=[])[1]

        logger.info(f"Extracted {len(hourly_records)} hourly records")

        # Store records
        stored = 0
        for record in hourly_records:
            await insert_hourly_usage(record)
            stored += 1
            logger.debug(f"Stored: {record.date} hour {record.hour}: {record.usage_litres}L")

        logger.info(f"Stored {stored} hourly records")

        # Show summary by date
        dates = set(r.date for r in hourly_records)
        logger.info(f"Dates with hourly data: {sorted(dates)}")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

    finally:
        await db.disconnect()


def main():
    """Main entry point."""
    asyncio.run(test_hourly_extraction())


if __name__ == "__main__":
    main()
