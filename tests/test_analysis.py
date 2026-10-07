import datetime as dt
import sys

sys.path.insert(0, "custom_components/thames_water_meter")
import importlib.util

spec = importlib.util.spec_from_file_location(
    "analysis", "custom_components/thames_water_meter/analysis.py"
)
a = importlib.util.module_from_spec(spec)
sys.modules["analysis"] = a
spec.loader.exec_module(a)
from thameswaterapi import (  # noqa: E402
    Line,
    lines_to_timeseries,
    meter_usage_lines_to_timeseries,
)

# hourly: end-of-hour reads
usage = [10, 0, 5, 20, 3]
reads, r = [], 1000
for u in usage:
    r += u
    reads.append(r)
lines = [
    Line(f"{i}:00", u, rd, False, "X") for i, (u, rd) in enumerate(zip(usage, reads, strict=True))
]
h = meter_usage_lines_to_timeseries(dt.date(2026, 10, 1), lines)
assert a.reads_are_start_of_hour(h) is False
assert a.cumulative_sum(h[2], False) == 1015

# hourly: start-of-hour reads
reads2 = [1000]
for u in usage[:-1]:
    reads2.append(reads2[-1] + u)
lines2 = [
    Line(f"{i}:00", u, rd, False, "X") for i, (u, rd) in enumerate(zip(usage, reads2, strict=True))
]
h2 = meter_usage_lines_to_timeseries(dt.date(2026, 10, 1), lines2)
assert a.reads_are_start_of_hour(h2) is True
assert a.cumulative_sum(h2[0], True) == 1010  # end of hour 0
# increments between consecutive sums equal each hour's usage
sums = [a.cumulative_sum(x, True) for x in h2]
assert [sums[i + 1] - sums[i] for i in range(4)] == usage[1:]

# daily
today = dt.date(2026, 10, 7)
dl = [Line(f"{d}-October", 100 + d, 5000 + d, False, "X") for d in range(1, 5)]
m = a.daily_metrics(lines_to_timeseries(dl))
assert m.latest_usage == 104 and m.month_days == 4 and m.month_to_date == 410, m
assert round(m.avg_7d, 1) == 102.5
assert m.month == "2026-10"

# data lag across a month boundary: the calendar month has no rows yet, so
# month-to-date must follow the latest data point instead of reading 0
dl2 = [Line(f"{d}-September", 100, 5000 + d, False, "X") for d in range(28, 31)]
m2 = a.daily_metrics(lines_to_timeseries(dl2))
assert m2.month == "2026-09" and m2.month_to_date == 300 and m2.month_days == 3, m2
assert a.cost(1000, 0.0040223, 0.532) == round(4.0223 + 0.532, 2)

# quietest hour: latest day with (nearly) all its hours; a partial newest day is skipped
from types import SimpleNamespace as N  # noqa: E402


def _day(d, count, quiet_hour):
    return [
        N(hour_start=dt.datetime(2026, 10, d, h, tzinfo=dt.UTC), usage=2 if h == quiet_hour else 20)
        for h in range(count)
    ]


quietest = a.minimum_hourly_usage(_day(3, 24, 4) + _day(4, 24, 2) + _day(5, 10, 1))
assert (quietest.date, quietest.usage, quietest.hour) == (dt.date(2026, 10, 4), 2.0, 2), quietest
assert a.minimum_hourly_usage(_day(5, 10, 1)) is None
assert a.minimum_hourly_usage([]) is None
# a clock-change day has 23 hours and still counts
assert a.minimum_hourly_usage(_day(5, 23, 7)).hour == 7
# tariff figures last a charging year, 1 April to 31 March
assert a.tariff_in_force(dt.date(2026, 4, 1), dt.date(2027, 3, 31))
assert not a.tariff_in_force(dt.date(2026, 4, 1), dt.date(2027, 4, 1))
assert a.tariff_in_force(dt.date(2026, 2, 1), dt.date(2026, 3, 31))  # still the 2025 year
assert not a.tariff_in_force(dt.date(2026, 2, 1), dt.date(2026, 4, 1))
assert a.tariff_in_force(dt.date(2026, 10, 7), dt.date(2026, 10, 7))
# merging windows: one row per hour, oldest first, a later window wins on overlap
older = [N(hour_start=dt.datetime(2026, 9, 1, 0, tzinfo=dt.UTC), usage=1)]
older.append(N(hour_start=dt.datetime(2026, 9, 1, 1, tzinfo=dt.UTC), usage=2))
recent = [N(hour_start=dt.datetime(2026, 9, 1, 1, tzinfo=dt.UTC), usage=20)]
recent.append(N(hour_start=dt.datetime(2026, 9, 1, 2, tzinfo=dt.UTC), usage=30))
merged = a.merge_hourly(recent, older)  # argument order must not decide the sort
assert [m.usage for m in merged] == [1, 2, 30], merged  # later argument (older) wins on overlap
merged = a.merge_hourly(older, recent)
assert [m.usage for m in merged] == [1, 20, 30], merged
assert a.merge_hourly([], []) == []
print("all good")
