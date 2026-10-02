"""Sanity checks applied to readings posted by the Hands adapter before they are stored."""

from datetime import datetime

from src.database.models import DailyUsage, HourlyUsage
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
