"""Pure helpers (no Home Assistant imports) so they can be unit-tested."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import Any


@dataclass
class DailyMetrics:
    """Summary figures derived from the daily series."""

    latest_date: dt.date | None
    latest_usage: float | None
    avg_7d: float | None
    month_to_date: float | None
    month_days: int


def daily_metrics(daily: list[Any], today: dt.date) -> DailyMetrics:
    """Compute headline figures from Measurement-like objects (start, usage)."""
    if not daily:
        return DailyMetrics(None, None, None, None, 0)
    daily = sorted(daily, key=lambda m: m.start)
    latest = daily[-1]
    last7 = daily[-7:]
    month = [m for m in daily if (m.start.year, m.start.month) == (today.year, today.month)]
    return DailyMetrics(
        latest_date=latest.start,
        latest_usage=float(latest.usage),
        avg_7d=sum(m.usage for m in last7) / len(last7),
        month_to_date=float(sum(m.usage for m in month)) if month else 0.0,
        month_days=len(month),
    )


def reads_are_start_of_hour(hours: list[Any]) -> bool:
    """Work out whether `total` is the meter read at the start or end of the hour.

    If read[i+1]-read[i] equals usage[i+1] the read is taken at the end of the
    hour; if it equals usage[i] it is taken at the start. Defaults to "end".
    """
    end_hits = start_hits = 0
    for a, b in zip(hours, hours[1:]):
        delta = b.total - a.total
        if delta == b.usage:
            end_hits += 1
        if delta == a.usage:
            start_hits += 1
    return start_hits > end_hits


def cumulative_sum(hour: Any, start_of_hour: bool) -> float:
    """Meter reading at the END of this hour (litres) - the statistics 'sum'."""
    return float(hour.total + (hour.usage if start_of_hour else 0))


def cost(litres: float | None, unit_rate_per_litre: float, standing_per_day: float) -> float | None:
    """Daily cost in GBP: volumetric charge plus the daily fixed charge."""
    if litres is None:
        return None
    return round(litres * unit_rate_per_litre + standing_per_day, 2)
