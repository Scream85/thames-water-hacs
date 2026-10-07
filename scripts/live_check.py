"""Read-only check of the real Thames Water API against this integration's assumptions.

Run it yourself so the password stays in your shell:

    THAMES_EMAIL=you@example.com THAMES_PASSWORD=... .venv/bin/python scripts/live_check.py

It logs in once, reads meters, daily and hourly usage and the tariff, then runs the
integration's own analysis helpers on the real data. It prints counts, dates and
litres only. The account number and meter id are masked, and the password is never
printed. Nothing is written to disk and nothing is changed at Thames Water.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import pathlib
import sys
import time

from thameswaterapi import (
    LONDON,
    AuthenticationError,
    MalformedResponse,
    RateLimitError,
    ThamesWater,
    lines_to_timeseries,
    meter_usage_lines_to_timeseries,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "analysis", ROOT / "custom_components" / "thames_water_meter" / "analysis.py"
)
analysis = importlib.util.module_from_spec(spec)
sys.modules["analysis"] = analysis
spec.loader.exec_module(analysis)

WINDOWS_DAYS = (7, 14, 30)
PAUSE_SECONDS = 3


def mask(value: object) -> str:
    text = str(value)
    return f"{'*' * max(len(text) - 2, 0)}{text[-2:]} (len {len(text)})"


def section(title: str) -> None:
    print(f"\n== {title}")


def main() -> int:
    email = os.environ.get("THAMES_EMAIL")
    password = os.environ.get("THAMES_PASSWORD")
    if not email or not password:
        print("Set THAMES_EMAIL and THAMES_PASSWORD in the environment.")
        return 2

    section("Login (full password login, fresh client)")
    client = ThamesWater(email=email, password=password)
    try:
        client.authenticate()
        meters = client.get_meters()
    except AuthenticationError as err:
        print(f"FAILED: login rejected ({type(err).__name__})")
        return 1
    except RateLimitError as err:
        print(f"FAILED: rate limited, retry after {getattr(err, 'retry_after', '?')}s")
        return 1
    except MalformedResponse as err:
        print(f"FAILED: unexpected page ({type(err).__name__}): {str(err)[:200]}")
        return 1
    print("login ok")
    print(f"account: {mask(client.account_number)}")
    print(f"meters: {len(meters.Meters)}", [mask(m) for m in meters.Meters])
    if not meters.Meters:
        return 1
    meter = meters.Meters[0]

    section("Daily series")
    daily = lines_to_timeseries(meters.Lines)
    print(f"rows: {len(daily)}")
    if daily:
        first, last = min(daily, key=lambda m: m.start), max(daily, key=lambda m: m.start)
        print(f"range: {first.start} .. {last.start}")
        today = dt.datetime.now(LONDON).date()
        print(f"data lag: latest day is {(today - last.start).days} days before today")
        print(f"start type: {type(last.start).__name__}")
        metrics = analysis.daily_metrics(daily)
        print(
            f"latest {metrics.latest_usage} L, 7-day avg {metrics.avg_7d:.0f} L, "
            f"month {metrics.month}: {metrics.month_to_date} L over {metrics.month_days} days"
        )

    section("Hourly windows (how much history does the API serve?)")
    end = dt.datetime.now(LONDON).date()
    hourly_by_window = {}
    for days in WINDOWS_DAYS:
        start = end - dt.timedelta(days=days)
        try:
            usage = client.get_meter_usage(meter, start, end, "H")
            hourly = meter_usage_lines_to_timeseries(start, usage.Lines)
        except Exception as err:  # noqa: BLE001 - report and carry on
            print(f"{days:>2} days: FAILED {type(err).__name__}: {str(err)[:150]}")
            continue
        real = [h for h in hourly if h.total > 0]
        hourly_by_window[days] = sorted(real, key=lambda h: h.hour_start)
        if real:
            hours = hourly_by_window[days]
            print(
                f"{days:>2} days: {len(hourly)} rows, {len(real)} with a meter read, "
                f"{hours[0].hour_start.isoformat()} .. {hours[-1].hour_start.isoformat()}, "
                f"{len({h.hour_start.date() for h in hours})} distinct days"
            )
        else:
            print(f"{days:>2} days: {len(hourly)} rows, none with a meter read")
        time.sleep(PAUSE_SECONDS)

    if not hourly_by_window:
        return 1
    widest = hourly_by_window[max(hourly_by_window)]
    if not widest:
        return 1
    sample = widest[-1]

    section("Hourly row checks")
    print(
        f"hour_start type: {type(sample.hour_start).__name__}, tzinfo: {sample.hour_start.tzinfo}"
    )
    print(f"sample row: usage={sample.usage} total={sample.total}")
    start_of_hour = analysis.reads_are_start_of_hour(widest)
    print(f"reads taken at: {'start' if start_of_hour else 'end'} of hour")
    sums = [analysis.cumulative_sum(h, start_of_hour) for h in widest]
    decreasing = sum(1 for a, b in zip(sums, sums[1:], strict=False) if b < a)
    print(f"cumulative sums decreasing {decreasing} times (expect 0)")
    gaps = sum(
        1
        for a, b in zip(widest, widest[1:], strict=False)
        if (b.hour_start - a.hour_start) != dt.timedelta(hours=1)
    )
    print(f"gaps between consecutive hours: {gaps}")
    steps = [(sums[i + 1] - sums[i], widest[i + 1].usage) for i in range(len(sums) - 1)]
    off = sum(1 for delta, used in steps if abs(delta - used) > 0.5)
    print(f"hours where read delta differs from usage: {off} of {len(steps)}")

    section("Hourly vs daily (are both in litres?)")
    by_day: dict[dt.date, float] = {}
    for h in widest:
        by_day[h.hour_start.date()] = by_day.get(h.hour_start.date(), 0.0) + h.usage
    daily_by_date = {m.start: m.usage for m in daily}
    compared = 0
    for day in sorted(by_day)[-5:]:
        if day in daily_by_date:
            compared += 1
            print(f"{day}: hourly sum {by_day[day]:.0f} L, daily {daily_by_date[day]:.0f} L")
    if not compared:
        print("no overlapping days to compare")

    section("Minimum hourly usage (new sensor)")
    minimum = analysis.minimum_hourly_usage(widest)
    print(minimum if minimum else "no complete day in the data")

    section("Tariff")
    try:
        tariff = client.get_tariff()
        print(
            f"unit rate {tariff.unit_rate_per_litre} GBP/L, "
            f"standing charge {tariff.standing_charge_per_day} GBP/day"
        )
    except Exception as err:  # noqa: BLE001 - TariffError or a network error
        print(f"tariff lookup failed: {type(err).__name__}: {str(err)[:150]}")

    print("\ndone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
