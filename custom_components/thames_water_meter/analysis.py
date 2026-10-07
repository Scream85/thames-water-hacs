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


@dataclass
class BillingPeriod:
    """Usage and cost over the bill's period, from the totals the integration already imports."""

    start: dt.date
    end: dt.date  # the last day counted
    days: int
    usage: float | None  # litres
    cost: float | None  # GBP
    closed: bool  # a past period, ended by the configured end date
    complete: bool  # the stored totals reach back to the start of the period


def billing_period(
    start: dt.date,
    end: dt.date | None,
    latest_day: dt.date,
    read_before_start: float | None,
    read_at_end: float | None,
    cost_before_start: float | None,
    cost_at_end: float | None,
) -> BillingPeriod:
    """Work out a billing period from running totals read before its start and at its end.

    Usage is the meter read at the end minus the read just before the first day. Cost is the
    running cost total in the same way, so both agree with the Energy dashboard. The data lags
    about three days, so an open period counts up to the latest day with data, and a period that
    has not reached any data yet has no figures. With an end date earlier than the latest data,
    the period is closed, which also makes it possible to check a past bill.
    """
    closed = end is not None and end < latest_day
    last_day = end if closed and end is not None else latest_day
    days = max((last_day - start).days + 1, 0)
    if days == 0:
        return BillingPeriod(start, last_day, 0, None, None, closed, False)
    usage = None
    if read_before_start is not None and read_at_end is not None:
        usage = max(read_at_end - read_before_start, 0.0)
    cost = None
    if cost_at_end is not None:
        cost = round(max(cost_at_end - (cost_before_start or 0.0), 0.0), 2)
    complete = read_before_start is not None and (cost_before_start is not None or cost is None)
    return BillingPeriod(start, last_day, days, usage, cost, closed, complete)


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


def _hours_in_local_day(hour_start: dt.datetime) -> float:
    """23, 24 or 25: how many hours the local day containing `hour_start` really has."""
    midnight = hour_start.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = midnight + dt.timedelta(days=1)  # wall-clock arithmetic in its own zone
    seconds = (next_midnight.astimezone(dt.UTC) - midnight.astimezone(dt.UTC)).total_seconds()
    return seconds / 3600


def hourly_costs(
    hours: list[Any],
    unit_rate_per_litre: float,
    standing_per_day: float,
    effective: dt.date,
) -> list[tuple[dt.datetime, float]]:
    """Cost in GBP of each hour: water used at the combined rate, plus its share of the day's
    standing charge.

    The standing charge is spread over the hours the local day really has, so a day's total is
    always the daily charge, even on the 23 and 25 hour days when the clocks change. Hours before
    the date the rates took effect get no cost, since the earlier rates are not known.
    """
    rows = []
    for hour in hours:
        if hour.hour_start.date() < effective:
            continue
        standing = standing_per_day / _hours_in_local_day(hour.hour_start)
        rows.append((hour.hour_start, hour.usage * unit_rate_per_litre + standing))
    return rows


def running_total(costs: list[tuple[dt.datetime, float]], base: float) -> list[float]:
    """The cumulative cost after each hour, continuing from `base`."""
    total = base
    totals = []
    for _start, cost in costs:
        total = round(total + cost, 6)
        totals.append(total)
    return totals


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
