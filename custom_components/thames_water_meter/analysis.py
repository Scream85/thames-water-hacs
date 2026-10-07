"""Pure helpers (no Home Assistant imports) so they can be unit-tested."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from itertools import pairwise
from typing import Any


@dataclass
class DailyMetrics:
    """Summary figures derived from the daily series."""

    latest_date: dt.date | None
    latest_usage: float | None
    avg_7d: float | None
    month_to_date: float | None
    month_days: int
    month: str | None = None


def daily_metrics(daily: list[Any]) -> DailyMetrics:
    """Compute headline figures from Measurement-like objects (start, usage).

    The data lags by about three days, so "month to date" is the month of the
    latest data point, not the calendar month. Otherwise it would read 0 for the
    first days of every month.
    """
    if not daily:
        return DailyMetrics(None, None, None, None, 0)
    daily = sorted(daily, key=lambda m: m.start)
    latest = daily[-1]
    last7 = daily[-7:]
    month = [
        m for m in daily if (m.start.year, m.start.month) == (latest.start.year, latest.start.month)
    ]
    return DailyMetrics(
        latest_date=latest.start,
        latest_usage=float(latest.usage),
        avg_7d=sum(m.usage for m in last7) / len(last7),
        month_to_date=float(sum(m.usage for m in month)),
        month_days=len(month),
        month=f"{latest.start.year:04d}-{latest.start.month:02d}",
    )


@dataclass
class HourlyMinimum:
    """The quietest hour of the latest complete day."""

    date: dt.date
    usage: float
    hour: int


# A day has 24 hourly rows, 23 or 25 across a clock change.
FULL_DAY_HOURS = 23


def minimum_hourly_usage(hours: list[Any]) -> HourlyMinimum | None:
    """Lowest hourly usage on the latest day that has (nearly) all its hours.

    Water used overnight is a leak indicator, so the minimum is the useful figure.
    A partial day is skipped, because its minimum only covers part of the day and
    would read as a quiet day. Ties go to the earliest hour.
    """
    by_day: dict[dt.date, list[Any]] = {}
    for h in hours:
        by_day.setdefault(h.hour_start.date(), []).append(h)
    full_days = [day for day, rows in by_day.items() if len(rows) >= FULL_DAY_HOURS]
    if not full_days:
        return None
    day = max(full_days)
    quietest = min(sorted(by_day[day], key=lambda h: h.hour_start), key=lambda h: h.usage)
    return HourlyMinimum(date=day, usage=float(quietest.usage), hour=quietest.hour_start.hour)


def tariff_in_force(effective: dt.date, today: dt.date) -> bool:
    """Whether charges that took effect on `effective` still apply on `today`.

    A charging year runs from 1 April to 31 March, so figures lapse on the first 1 April
    after the charging year they started in.
    """
    start_year = effective.year if effective.month >= 4 else effective.year - 1
    return today < dt.date(start_year + 1, 4, 1)


def merge_hourly(*windows: list[Any]) -> list[Any]:
    """Join hourly windows into one list, oldest first, one row per hour.

    Where windows overlap, a row from a later window wins, so the freshest figure is kept.
    """
    by_hour: dict[Any, Any] = {}
    for window in windows:
        for row in window:
            by_hour[row.hour_start] = row
    return [by_hour[hour] for hour in sorted(by_hour)]


def reads_are_start_of_hour(hours: list[Any]) -> bool:
    """Work out whether `total` is the meter read at the start or end of the hour.

    If read[i+1]-read[i] equals usage[i+1] the read is taken at the end of the
    hour; if it equals usage[i] it is taken at the start. Defaults to "end".
    """
    end_hits = start_hits = 0
    for a, b in pairwise(hours):
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
