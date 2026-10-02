"""Scheduled job definitions."""

import time
from datetime import datetime, timedelta, timezone

from src.config import get_settings
from src.database.models import Alert, DailyUsage, SyncLog
from src.database.queries import (
    alert_exists,
    create_alert,
    create_sync_log,
    get_daily_usage,
    get_hourly_sum,
    get_meter_readings_for_date,
    get_previous_day_end_reading,
    insert_daily_usage,
    mark_alert_notified,
)
from src.notifications.email import send_alert_email
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
