import datetime as dt, sys
sys.path.insert(0, "custom_components/thames_water_meter")
import importlib.util
spec = importlib.util.spec_from_file_location("analysis", "custom_components/thames_water_meter/analysis.py")
a = importlib.util.module_from_spec(spec); sys.modules['analysis'] = a; spec.loader.exec_module(a)
from thameswaterapi import Line, meter_usage_lines_to_timeseries, lines_to_timeseries

# hourly: end-of-hour reads
usage = [10, 0, 5, 20, 3]
reads, r = [], 1000
for u in usage:
    r += u; reads.append(r)
lines = [Line(f"{i}:00", u, rd, False, "X") for i, (u, rd) in enumerate(zip(usage, reads))]
h = meter_usage_lines_to_timeseries(dt.date(2026, 10, 1), lines)
assert a.reads_are_start_of_hour(h) is False
assert a.cumulative_sum(h[2], False) == 1015

# hourly: start-of-hour reads
reads2 = [1000]
for u in usage[:-1]: reads2.append(reads2[-1] + u)
lines2 = [Line(f"{i}:00", u, rd, False, "X") for i, (u, rd) in enumerate(zip(usage, reads2))]
h2 = meter_usage_lines_to_timeseries(dt.date(2026, 10, 1), lines2)
assert a.reads_are_start_of_hour(h2) is True
assert a.cumulative_sum(h2[0], True) == 1010   # end of hour 0
# increments between consecutive sums equal each hour's usage
sums = [a.cumulative_sum(x, True) for x in h2]
assert [sums[i+1]-sums[i] for i in range(4)] == usage[1:]

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
print("all good")
