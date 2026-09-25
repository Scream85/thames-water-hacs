"""Data access layer for Thames Water database."""

from datetime import datetime, timezone
from typing import Literal

from src.database.connection import get_database
from src.database.models import (
    Alert,
    DailyUsage,
    HourlyUsage,
    MonthlyUsage,
    SyncLog,
    UsageSummary,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Daily Usage Queries
# =============================================================================


async def insert_daily_usage(usage: DailyUsage) -> int:
    """Insert or update daily usage record."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        """
        INSERT INTO daily_usage (date, usage_litres, meter_reading, is_estimated,
                                 hourly_sum, verified, source, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            usage_litres = excluded.usage_litres,
            meter_reading = excluded.meter_reading,
            is_estimated = excluded.is_estimated,
            hourly_sum = excluded.hourly_sum,
            verified = excluded.verified,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        (
            usage.date,
            usage.usage_litres,
            usage.meter_reading,
            usage.is_estimated,
            usage.hourly_sum,
            usage.verified,
            usage.source,
            now,
            now,
        ),
    )

    result = await db.fetch_one(
        "SELECT id FROM daily_usage WHERE date = ?", (usage.date,)
    )
    return result["id"] if result else 0


async def get_daily_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get daily usage records with optional date range."""
    db = get_database()

    conditions = []
    params: list = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT * FROM daily_usage
        {where_clause}
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    return await db.fetch_all(query, tuple(params))


async def get_daily_usage_count(
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """Get count of daily usage records."""
    db = get_database()

    conditions = []
    params: list = []

    if start_date:
        conditions.append("date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("date <= ?")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.fetch_one(
        f"SELECT COUNT(*) as count FROM daily_usage {where_clause}",
        tuple(params) if params else None,
    )
    return result["count"] if result else 0


async def get_usage_summary(days: int = 30) -> UsageSummary:
    """Get usage summary for the specified number of days."""
    db = get_database()

    result = await db.fetch_one(
        """
        SELECT
            COUNT(*) as days_recorded,
            SUM(usage_litres) as total_litres,
            AVG(usage_litres) as average_daily,
            MAX(usage_litres) as max_daily,
            MIN(usage_litres) as min_daily,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM (
            SELECT * FROM daily_usage
            ORDER BY date DESC
            LIMIT ?
        )
        """,
        (days,),
    )

    if not result or result["days_recorded"] == 0:
        return UsageSummary(
            period=f"{days} days",
            total_litres=0,
            average_daily=0,
            max_daily=0,
            min_daily=0,
            days_recorded=0,
        )

    # Count days above threshold
    from src.config import get_settings
    threshold = get_settings().spike_threshold

    threshold_result = await db.fetch_one(
        """
        SELECT COUNT(*) as count FROM (
            SELECT * FROM daily_usage
            ORDER BY date DESC
            LIMIT ?
        ) WHERE usage_litres > ?
        """,
        (days, threshold),
    )

    # Calculate trend (compare first half to second half)
    half_days = days // 2
    trend_result = await db.fetch_one(
        """
        WITH recent AS (
            SELECT usage_litres, ROW_NUMBER() OVER (ORDER BY date DESC) as rn
            FROM daily_usage
            ORDER BY date DESC
            LIMIT ?
        )
        SELECT
            AVG(CASE WHEN rn <= ? THEN usage_litres END) as recent_avg,
            AVG(CASE WHEN rn > ? THEN usage_litres END) as older_avg
        FROM recent
        """,
        (days, half_days, half_days),
    )

    trend: Literal["rising", "falling", "stable"] = "stable"
    if trend_result and trend_result["recent_avg"] and trend_result["older_avg"]:
        diff = trend_result["recent_avg"] - trend_result["older_avg"]
        if diff > 50:  # More than 50L/day increase
            trend = "rising"
        elif diff < -50:  # More than 50L/day decrease
            trend = "falling"

    return UsageSummary(
        period=f"{days} days",
        total_litres=result["total_litres"] or 0,
        average_daily=result["average_daily"] or 0,
        max_daily=result["max_daily"] or 0,
        min_daily=result["min_daily"] or 0,
        days_recorded=result["days_recorded"],
        days_above_threshold=threshold_result["count"] if threshold_result else 0,
        trend=trend,
        date_range={
            "start": result["start_date"],
            "end": result["end_date"],
        } if result["start_date"] else None,
    )


async def get_monthly_usage(year: int | None = None) -> list[MonthlyUsage]:
    """Get monthly usage aggregates."""
    db = get_database()

    where_clause = ""
    params: tuple = ()
    if year:
        where_clause = "WHERE date LIKE ?"
        params = (f"{year}-%",)

    rows = await db.fetch_all(
        f"""
        SELECT
            strftime('%Y-%m', date) as month,
            SUM(usage_litres) as total_litres,
            AVG(usage_litres) as average_daily,
            COUNT(*) as days_recorded,
            MAX(usage_litres) as max_daily,
            MIN(usage_litres) as min_daily
        FROM daily_usage
        {where_clause}
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
        """,
        params if params else None,
    )

    return [
        MonthlyUsage(
            month=row["month"],
            total_litres=row["total_litres"],
            average_daily=row["average_daily"],
            days_recorded=row["days_recorded"],
            max_daily=row["max_daily"],
            min_daily=row["min_daily"],
        )
        for row in rows
    ]


# =============================================================================
# Hourly Usage Queries
# =============================================================================


async def insert_hourly_usage(usage: HourlyUsage) -> int:
    """Insert or update hourly usage record."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        """
        INSERT INTO hourly_usage (date, hour, usage_litres, meter_reading,
                                  is_estimated, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, hour) DO UPDATE SET
            usage_litres = excluded.usage_litres,
            meter_reading = excluded.meter_reading,
            is_estimated = excluded.is_estimated,
            source = excluded.source
        """,
        (
            usage.date,
            usage.hour,
            usage.usage_litres,
            usage.meter_reading,
            usage.is_estimated,
            usage.source,
            now,
        ),
    )

    result = await db.fetch_one(
        "SELECT id FROM hourly_usage WHERE date = ? AND hour = ?",
        (usage.date, usage.hour),
    )
    return result["id"] if result else 0


async def get_hourly_usage(date: str) -> list[dict]:
    """Get hourly usage for a specific date."""
    db = get_database()
    return await db.fetch_all(
        "SELECT * FROM hourly_usage WHERE date = ? ORDER BY hour",
        (date,),
    )


async def get_hourly_sum(date: str) -> float:
    """Get sum of hourly usage for a date."""
    db = get_database()
    result = await db.fetch_one(
        "SELECT SUM(usage_litres) as total FROM hourly_usage WHERE date = ?",
        (date,),
    )
    return result["total"] if result and result["total"] else 0


async def get_meter_readings_for_date(date: str) -> dict | None:
    """
    Get meter readings for a specific date.

    Returns:
        Dictionary with:
        - first_reading: Meter reading at hour 00
        - last_reading: Meter reading at hour 23
        - meter_change: Difference (actual usage based on meter)
        - hourly_count: Number of hourly records with readings
        Or None if no data available
    """
    db = get_database()

    result = await db.fetch_one(
        """
        SELECT
            MIN(CASE WHEN hour = 0 THEN meter_reading END) as first_reading,
            MAX(CASE WHEN hour = 23 THEN meter_reading END) as last_reading,
            COUNT(CASE WHEN meter_reading IS NOT NULL THEN 1 END) as hourly_count
        FROM hourly_usage
        WHERE date = ?
        """,
        (date,),
    )

    if not result or result["first_reading"] is None or result["last_reading"] is None:
        return None

    return {
        "first_reading": result["first_reading"],
        "last_reading": result["last_reading"],
        "meter_change": result["last_reading"] - result["first_reading"],
        "hourly_count": result["hourly_count"],
    }


async def get_previous_day_end_reading(date: str) -> float | None:
    """
    Get the meter reading at hour 23 of the previous day.

    This is used to calculate the overnight gap between days.
    """
    db = get_database()
    from datetime import datetime, timedelta

    # Parse date and get previous day
    dt = datetime.strptime(date, "%Y-%m-%d")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

    result = await db.fetch_one(
        "SELECT meter_reading FROM hourly_usage WHERE date = ? AND hour = 23",
        (prev_date,),
    )

    return result["meter_reading"] if result and result["meter_reading"] else None


# =============================================================================
# Alert Queries
# =============================================================================


async def alert_exists(alert_type: str, alert_date: str) -> bool:
    """Check if an alert already exists for a specific type and date."""
    db = get_database()
    result = await db.fetch_one(
        "SELECT id FROM alerts WHERE alert_type = ? AND alert_date = ?",
        (alert_type, alert_date),
    )
    return result is not None


async def create_alert(alert: Alert) -> int:
    """Create a new alert."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        """
        INSERT INTO alerts (alert_type, alert_date, message, value, threshold,
                           notified, notified_at, acknowledged, acknowledged_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert.alert_type,
            alert.alert_date,
            alert.message,
            alert.value,
            alert.threshold,
            alert.notified,
            alert.notified_at.isoformat() if alert.notified_at else None,
            alert.acknowledged,
            alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            now,
        ),
    )

    result = await db.fetch_one("SELECT last_insert_rowid() as id")
    return result["id"] if result else 0


async def get_alerts(
    status: Literal["all", "unacknowledged", "acknowledged"] = "all",
    limit: int = 20,
) -> list[dict]:
    """Get alerts with optional status filter."""
    db = get_database()

    where_clause = ""
    if status == "unacknowledged":
        where_clause = "WHERE acknowledged = FALSE"
    elif status == "acknowledged":
        where_clause = "WHERE acknowledged = TRUE"

    return await db.fetch_all(
        f"""
        SELECT * FROM alerts
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )


async def acknowledge_alert(alert_id: int) -> bool:
    """Mark an alert as acknowledged."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        "UPDATE alerts SET acknowledged = TRUE, acknowledged_at = ? WHERE id = ?",
        (now, alert_id),
    )
    return True


async def mark_alert_notified(alert_id: int) -> bool:
    """Mark an alert as notified."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        "UPDATE alerts SET notified = TRUE, notified_at = ? WHERE id = ?",
        (now, alert_id),
    )
    return True


# =============================================================================
# Sync Log Queries
# =============================================================================


async def create_sync_log(log: SyncLog) -> int:
    """Create a sync log entry."""
    db = get_database()
    now = _now_iso()

    await db.execute(
        """
        INSERT INTO sync_log (sync_type, source, sync_time, status, records_fetched,
                             records_stored, date_range_start, date_range_end,
                             error_message, retry_count, duration_seconds, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            log.sync_type,
            log.source,
            log.sync_time.isoformat(),
            log.status,
            log.records_fetched,
            log.records_stored,
            log.date_range_start,
            log.date_range_end,
            log.error_message,
            log.retry_count,
            log.duration_seconds,
            now,
        ),
    )

    result = await db.fetch_one("SELECT last_insert_rowid() as id")
    return result["id"] if result else 0


async def get_last_sync(
    sync_type: str | None = None,
) -> dict | None:
    """Get the last sync log entry."""
    db = get_database()

    if sync_type:
        return await db.fetch_one(
            "SELECT * FROM sync_log WHERE sync_type = ? ORDER BY sync_time DESC LIMIT 1",
            (sync_type,),
        )
    return await db.fetch_one(
        "SELECT * FROM sync_log ORDER BY sync_time DESC LIMIT 1"
    )


async def get_recent_sync_errors(limit: int = 5) -> list[dict]:
    """Get recent sync errors."""
    db = get_database()
    return await db.fetch_all(
        """
        SELECT * FROM sync_log
        WHERE status = 'error'
        ORDER BY sync_time DESC
        LIMIT ?
        """,
        (limit,),
    )
