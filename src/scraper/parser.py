"""Data parsing utilities for Thames Water scraper."""

from datetime import datetime
from typing import Any

from src.database.models import DailyUsage, HourlyUsage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Month name to number mapping
MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
    # Short forms
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_date_label(label: str, year: int | None = None) -> str | None:
    """
    Convert Thames Water date label to ISO format.

    Examples:
        "15-November" -> "2025-11-15"
        "1-December" -> "2025-12-01"

    Args:
        label: Date label like "15-November"
        year: Year to use (defaults to current year)

    Returns:
        ISO format date string or None if parsing fails
    """
    try:
        parts = label.split("-")
        if len(parts) != 2:
            return None

        day = int(parts[0])
        month_name = parts[1]
        month_num = MONTH_MAP.get(month_name)

        if not month_num:
            logger.warning(f"Unknown month name: {month_name}")
            return None

        if year is None:
            year = datetime.now().year

        return f"{year}-{month_num:02d}-{day:02d}"

    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse date label '{label}': {e}")
        return None


def parse_month_year(month_str: str) -> tuple[int, int] | None:
    """
    Parse month-year string to (month, year) tuple.

    Examples:
        "Dec-2024" -> (12, 2024)
        "Nov-2025" -> (11, 2025)
    """
    try:
        parts = month_str.split("-")
        if len(parts) != 2:
            return None

        month_name = parts[0]
        year = int(parts[1])
        month_num = MONTH_MAP.get(month_name)

        if not month_num:
            return None

        return (month_num, year)

    except (ValueError, IndexError):
        return None


def parse_daily_consumption(data: dict[str, Any], source: str = "scraper") -> DailyUsage | None:
    """
    Parse raw consumption data into DailyUsage model.

    Expected fields:
        - Label: Date label (e.g., "15-November")
        - Usage: Usage in litres
        - Read: Meter reading
        - IsEstimated: Whether reading is estimated
    """
    try:
        label = data.get("Label", "")
        date = parse_date_label(label)

        if not date:
            logger.warning(f"Could not parse date from label: {label}")
            return None

        usage = float(data.get("Usage", 0))
        reading = data.get("Read")
        is_estimated = data.get("IsEstimated", False)

        return DailyUsage(
            date=date,
            usage_litres=usage,
            meter_reading=float(reading) if reading else None,
            is_estimated=bool(is_estimated),
            source=source,
        )

    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse daily consumption: {e}")
        return None


def parse_hourly_consumption(
    data: dict[str, Any],
    date: str,
    source: str = "scraper"
) -> list[HourlyUsage]:
    """
    Parse hourly consumption data.

    Expected data format may vary - this handles multiple formats.
    """
    hourly_records = []

    try:
        # Format 1: List of hourly values
        if isinstance(data, list):
            for hour, value in enumerate(data):
                if hour > 23:
                    break
                hourly_records.append(HourlyUsage(
                    date=date,
                    hour=hour,
                    usage_litres=float(value),
                    source=source,
                ))

        # Format 2: Dict with hour keys
        elif isinstance(data, dict):
            for key, value in data.items():
                try:
                    hour = int(key)
                    if 0 <= hour <= 23:
                        hourly_records.append(HourlyUsage(
                            date=date,
                            hour=hour,
                            usage_litres=float(value.get("Usage", value) if isinstance(value, dict) else value),
                            source=source,
                        ))
                except (ValueError, TypeError):
                    continue

    except Exception as e:
        logger.warning(f"Failed to parse hourly consumption: {e}")

    return hourly_records


def validate_daily_usage(usage: DailyUsage) -> bool:
    """Validate daily usage data."""
    # Check date format
    try:
        datetime.strptime(usage.date, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: {usage.date}")
        return False

    # Check usage is non-negative
    if usage.usage_litres < 0:
        logger.warning(f"Negative usage: {usage.usage_litres}")
        return False

    # Check for unreasonably high usage (> 50,000 L/day)
    if usage.usage_litres > 50000:
        logger.warning(f"Suspiciously high usage: {usage.usage_litres}")
        # Don't reject, just warn

    return True


def validate_hourly_usage(usage: HourlyUsage) -> bool:
    """Validate hourly usage data."""
    # Check date format
    try:
        datetime.strptime(usage.date, "%Y-%m-%d")
    except ValueError:
        return False

    # Check hour range
    if not 0 <= usage.hour <= 23:
        return False

    # Check usage is non-negative
    if usage.usage_litres < 0:
        return False

    return True
