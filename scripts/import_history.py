#!/usr/bin/env python3
"""Import historical water usage data from CSV."""

import asyncio
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import get_database
from src.database.models import DailyUsage, SyncLog
from src.database.queries import insert_daily_usage, create_sync_log
from src.utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def import_csv(csv_path: str) -> None:
    """
    Import historical data from CSV file.

    Args:
        csv_path: Path to CSV file with columns:
            Date, Date_Label, Month, Usage_Litres, Meter_Reading, Is_Estimated
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    logger.info(f"Importing data from {csv_path}")

    # Connect to database
    db = get_database()
    await db.connect()

    try:
        records_imported = 0
        records_skipped = 0

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Parse the row
                    date = row['Date']
                    usage = float(row['Usage_Litres'])
                    meter_reading = float(row['Meter_Reading']) if row.get('Meter_Reading') else None
                    is_estimated = row.get('Is_Estimated', 'False').lower() == 'true'

                    # Create record
                    record = DailyUsage(
                        date=date,
                        usage_litres=usage,
                        meter_reading=meter_reading,
                        is_estimated=is_estimated,
                        verified=True,  # Historical data is verified
                        source='csv_import',
                    )

                    await insert_daily_usage(record)
                    records_imported += 1

                    if records_imported % 50 == 0:
                        logger.info(f"Imported {records_imported} records...")

                except Exception as e:
                    logger.warning(f"Skipping row {row.get('Date', 'unknown')}: {e}")
                    records_skipped += 1

        # Create sync log for the import
        sync_log = SyncLog(
            sync_type='csv_import',
            sync_time=datetime.now(timezone.utc),
            status='success',
            records_fetched=records_imported + records_skipped,
            records_stored=records_imported,
        )
        await create_sync_log(sync_log)

        logger.info(
            f"Import complete: {records_imported} records imported, {records_skipped} skipped"
        )

    finally:
        await db.disconnect()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        # Default to the existing CSV location
        default_csv = Path(__file__).parent.parent.parent.parent / \
            "integrations/thames-water/full_history.csv"
        csv_path = str(default_csv)
    else:
        csv_path = sys.argv[1]

    asyncio.run(import_csv(csv_path))


if __name__ == "__main__":
    main()
