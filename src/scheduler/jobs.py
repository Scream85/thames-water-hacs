"""Scheduled job definitions."""

import time
from datetime import datetime, timedelta, timezone

from src.config import get_settings
from src.database.models import Alert, DailyUsage, HourlyUsage, SyncLog
from src.database.queries import (
    alert_exists,
    create_alert,
    create_sync_log,
    get_daily_usage,
    get_hourly_sum,
    get_meter_readings_for_date,
    get_previous_day_end_reading,
    insert_daily_usage,
    insert_hourly_usage,
    mark_alert_notified,
)
from src.notifications.email import send_alert_email, send_error_notification
from src.scraper.extractor import ThamesWaterExtractor
from src.scraper.exceptions import ScraperError
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def daily_hourly_fetch_job() -> None:
    """
    Daily job to fetch latest daily and hourly data.

    Runs at 6:00 AM daily (configurable).
    Uses simplified workflow:
    1. "Monthly (by days)" + "Last 30 days" for daily data
    2. "Daily (by hours)" + latest date for hourly data
    """
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Starting daily sync for {today}")

    sync_log = SyncLog(
        sync_type="daily",
        sync_time=datetime.now(timezone.utc),
        status="success",
    )

    try:
        extractor = ThamesWaterExtractor()
        daily_records, hourly_records, attempted_hourly_date = extractor.run_daily_sync()

        # Store daily records (only new ones)
        daily_stored = 0
        latest_date = None
        for record in daily_records:
            # Check if we already have this record
            existing = await get_daily_usage(
                start_date=record.date,
                end_date=record.date,
                limit=1
            )
            if not existing:
                await insert_daily_usage(record)
                daily_stored += 1
                await check_for_spike(record)

            # Track date range
            if latest_date is None or record.date > latest_date:
                latest_date = record.date

        # Store hourly records
        hourly_stored = 0
        hourly_date = None
        for record in hourly_records:
            await insert_hourly_usage(record)
            hourly_stored += 1
            hourly_date = record.date  # Track which date we got data for

        # Create alert if hourly data was unavailable for the attempted date
        if not hourly_records and attempted_hourly_date:
            logger.warning(
                f"No hourly data available for {attempted_hourly_date}",
                extra={"attempted_date": attempted_hourly_date}
            )
            # Check if we already have an alert for this date
            if not await alert_exists("data_unavailable", attempted_hourly_date):
                alert = Alert(
                    alert_type="data_unavailable",
                    alert_date=attempted_hourly_date,
                    message=f"Thames Water has no hourly data available for {attempted_hourly_date}",
                    value=None,
                )
                await create_alert(alert)

        # Create alert if data became available (we got data AND previously had data_unavailable)
        if hourly_records and hourly_date:
            # Check if we previously flagged this date as unavailable
            if await alert_exists("data_unavailable", hourly_date):
                # Data is now available! Log when it became available
                if not await alert_exists("data_available", hourly_date):
                    logger.info(
                        f"Data now available for {hourly_date}",
                        extra={"date": hourly_date, "records": hourly_stored}
                    )
                    alert = Alert(
                        alert_type="data_available",
                        alert_date=hourly_date,
                        message=f"Thames Water hourly data is now available for {hourly_date} ({hourly_stored} records)",
                        value=float(hourly_stored),
                    )
                    await create_alert(alert)

        sync_log.records_fetched = len(daily_records) + len(hourly_records)
        sync_log.records_stored = daily_stored + hourly_stored

        if daily_records:
            sync_log.date_range_start = min(r.date for r in daily_records)
            sync_log.date_range_end = max(r.date for r in daily_records)

        logger.info(
            f"Daily sync complete",
            extra={
                "daily_fetched": len(daily_records),
                "daily_stored": daily_stored,
                "hourly_fetched": len(hourly_records),
                "hourly_stored": hourly_stored,
                "latest_date": latest_date,
            }
        )

    except ScraperError as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        logger.error(f"Daily fetch failed: {e}")

        # Send error notification
        await send_error_notification(
            error_type="Daily Sync Failed",
            error_message=str(e),
            date=yesterday,
        )

    except Exception as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        logger.error(f"Daily fetch failed with unexpected error: {e}")

        await send_error_notification(
            error_type="Daily Sync Error",
            error_message=str(e),
            date=yesterday,
        )

    finally:
        sync_log.duration_seconds = time.time() - start_time
        await create_sync_log(sync_log)


async def weekly_verification_job() -> None:
    """
    Weekly job to verify data quality using meter readings.

    Runs every Sunday at 7:00 AM (configurable).
    Checks the past 7 days of data.

    Verification approach:
    1. PRIMARY: Compare daily reported usage with meter reading change (should match exactly)
    2. SECONDARY: Compare hourly sum with meter reading change (explains boundary allocation)
    3. Calculate overnight gaps between days to explain discrepancies
    """
    start_time = time.time()
    logger.info("Starting weekly verification with meter-based comparison")

    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    sync_log = SyncLog(
        sync_type="weekly_verify",
        sync_time=datetime.now(timezone.utc),
        status="success",
        date_range_start=week_ago,
        date_range_end=today_str,
    )

    mismatches = []
    verified_count = 0
    no_meter_data_count = 0

    try:
        # Get daily records for the past week
        daily_records = await get_daily_usage(
            start_date=week_ago,
            end_date=today_str,
            limit=10,
        )

        for record in daily_records:
            date = record["date"]
            daily_usage = record["usage_litres"]
            hourly_sum = await get_hourly_sum(date)
            meter_data = await get_meter_readings_for_date(date)
            prev_day_reading = await get_previous_day_end_reading(date)

            # Calculate verification metrics
            verification_result = {
                "date": date,
                "daily_reported": daily_usage,
                "hourly_sum": hourly_sum,
                "meter_change": None,
                "overnight_gap": None,
                "meter_verified": False,
                "explanation": None,
            }

            if meter_data:
                meter_change = meter_data["meter_change"]
                verification_result["meter_change"] = meter_change

                # Calculate overnight gap (usage between previous day end and current day start)
                if prev_day_reading is not None:
                    overnight_gap = meter_data["first_reading"] - prev_day_reading
                    verification_result["overnight_gap"] = overnight_gap

                # PRIMARY CHECK: Daily usage should match meter change (within 1L tolerance)
                daily_vs_meter_diff = abs(daily_usage - meter_change)
                if daily_vs_meter_diff <= 1:
                    verification_result["meter_verified"] = True
                    verified_count += 1

                    # Explain hourly sum discrepancy if exists
                    hourly_vs_meter_diff = hourly_sum - meter_change
                    if abs(hourly_vs_meter_diff) > 1:
                        verification_result["explanation"] = (
                            f"Hourly sum ({hourly_sum}L) differs from meter change ({meter_change}L) by "
                            f"{hourly_vs_meter_diff:.0f}L due to overnight boundary allocation"
                        )
                else:
                    # Daily doesn't match meter - this is unexpected
                    verification_result["explanation"] = (
                        f"UNEXPECTED: Daily ({daily_usage}L) differs from meter change ({meter_change}L) by "
                        f"{daily_vs_meter_diff:.0f}L"
                    )
                    mismatches.append(verification_result)

                # Update daily record with verification data
                updated = DailyUsage(
                    date=date,
                    usage_litres=daily_usage,
                    meter_reading=meter_data["last_reading"],
                    hourly_sum=hourly_sum,
                    verified=verification_result["meter_verified"],
                    source="scraper",
                )
                await insert_daily_usage(updated)

                logger.info(
                    f"Verified {date}: daily={daily_usage}L, meter_change={meter_change}L, "
                    f"hourly_sum={hourly_sum}L, overnight_gap={verification_result['overnight_gap']}L, "
                    f"verified={verification_result['meter_verified']}"
                )

            else:
                # No meter data available
                no_meter_data_count += 1
                verification_result["explanation"] = "No meter reading data available"

                # Fall back to hourly sum comparison (5% tolerance)
                if hourly_sum > 0:
                    diff = abs(daily_usage - hourly_sum)
                    tolerance = daily_usage * 0.05
                    is_verified = diff <= tolerance

                    updated = DailyUsage(
                        date=date,
                        usage_litres=daily_usage,
                        hourly_sum=hourly_sum,
                        verified=is_verified,
                        source="scraper",
                    )
                    await insert_daily_usage(updated)

                    if not is_verified:
                        mismatches.append(verification_result)
                    else:
                        verified_count += 1

        sync_log.records_fetched = len(daily_records)
        sync_log.records_stored = verified_count

        if mismatches:
            sync_log.status = "partial"
            logger.warning(f"Found {len(mismatches)} verification issues (meter-based)")

            # Create alert for significant mismatches only
            for mismatch in mismatches:
                if mismatch["meter_change"] is not None:
                    # Meter-based mismatch - this is concerning
                    alert = Alert(
                        alert_type="verification_mismatch",
                        alert_date=mismatch["date"],
                        message=f"[METER] {mismatch['explanation']}",
                        value=abs(mismatch["daily_reported"] - mismatch["meter_change"]),
                    )
                    await create_alert(alert)
        else:
            logger.info(
                f"Weekly verification complete - {verified_count} records verified via meter readings, "
                f"{no_meter_data_count} records without meter data"
            )

    except Exception as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        logger.error(f"Weekly verification failed: {e}")

    finally:
        sync_log.duration_seconds = time.time() - start_time
        await create_sync_log(sync_log)


async def check_for_spike(usage: DailyUsage) -> None:
    """
    Check if daily usage exceeds threshold and create alert.

    Args:
        usage: Daily usage record to check
    """
    settings = get_settings()
    threshold = settings.spike_threshold

    if usage.usage_litres > threshold:
        # Check if alert already exists for this date
        if await alert_exists("spike", usage.date):
            logger.debug(f"Spike alert already exists for {usage.date}, skipping")
            return

        logger.warning(
            f"Spike detected: {usage.usage_litres}L on {usage.date}",
            extra={"threshold": threshold}
        )

        alert = Alert(
            alert_type="spike",
            alert_date=usage.date,
            message=f"Daily usage of {usage.usage_litres:.0f}L exceeded threshold of {threshold}L",
            value=usage.usage_litres,
            threshold=float(threshold),
        )
        alert_id = await create_alert(alert)

        # Send notification
        try:
            await send_alert_email(
                subject=f"Thames Water Alert: High Usage on {usage.date}",
                body=f"""
Water usage spike detected!

Date: {usage.date}
Usage: {usage.usage_litres:.0f} litres
Threshold: {threshold} litres
Excess: {usage.usage_litres - threshold:.0f} litres

This could indicate:
- A leak or running tap
- Unusual household activity
- Irrigation system running too long

Please check your water usage.

View details: https://water.gavinslater.co.uk
                """.strip(),
            )
            await mark_alert_notified(alert_id)
            logger.info(f"Spike alert sent for {usage.date}")

        except Exception as e:
            logger.error(f"Failed to send spike alert: {e}")


async def fetch_hourly_for_date(date: str) -> None:
    """
    Fetch hourly data for a specific date.

    Args:
        date: Date in YYYY-MM-DD format
    """
    logger.info(f"Fetching hourly data for {date}")

    try:
        extractor = ThamesWaterExtractor()
        _, hourly_records = extractor.run(include_hourly=True)

        records_stored = 0
        for record in hourly_records:
            if record.date == date:
                await insert_hourly_usage(record)
                records_stored += 1

        logger.info(f"Stored {records_stored} hourly records for {date}")

    except Exception as e:
        logger.error(f"Failed to fetch hourly data for {date}: {e}")
        raise


async def backfill_job() -> None:
    """
    Backfill job to fetch all available historical data.

    This runs the full extraction for all available months.
    """
    start_time = time.time()
    logger.info("Starting backfill job")

    sync_log = SyncLog(
        sync_type="backfill",
        sync_time=datetime.now(timezone.utc),
        status="success",
    )

    try:
        extractor = ThamesWaterExtractor()

        # Generate months to extract (Dec 2024 - current)
        months = [
            "Dec-2024", "Jan-2025", "Feb-2025", "Mar-2025",
            "Apr-2025", "May-2025", "Jun-2025", "Jul-2025",
            "Aug-2025", "Sep-2025", "Oct-2025", "Nov-2025", "Dec-2025",
        ]

        daily_records, _ = extractor.run(months=months)

        records_stored = 0
        for record in daily_records:
            await insert_daily_usage(record)
            records_stored += 1

            # Check for spike
            await check_for_spike(record)

        sync_log.records_fetched = len(daily_records)
        sync_log.records_stored = records_stored

        if daily_records:
            sync_log.date_range_start = daily_records[0].date
            sync_log.date_range_end = daily_records[-1].date

        logger.info(f"Backfill complete: {records_stored} records stored")

    except Exception as e:
        sync_log.status = "error"
        sync_log.error_message = str(e)
        logger.error(f"Backfill failed: {e}")

    finally:
        sync_log.duration_seconds = time.time() - start_time
        await create_sync_log(sync_log)
