# Thames Water Monitoring Service

## Overview

Automated water usage monitoring system for Thames Water smart meter data with REST API, dashboard, cost tracking, and alerting.

## Quick Reference

- **Port**: 8096
- **Dashboard**: https://water.gavinslater.co.uk
- **API Docs**: https://water.gavinslater.co.uk/docs
- **Spike Threshold**: 800L (triggers alerts)
- **Data Collection**: Daily at 6 AM
- **Data Delay**: ~3 days (Thames Water limitation)

## Architecture

```
FastAPI Application
├── API Endpoints (/api/*)
├── Dashboard (static HTML + Chart.js)
│   ├── Usage Cards (Latest Day, 7-Day Avg, This Month, Alerts)
│   ├── Cost Cards (Daily, Month to Date, Projected, Annual)
│   ├── Daily Chart (30/90/365 days)
│   ├── Hourly Chart (per-day breakdown)
│   └── Monthly Chart (year comparison)
├── Scheduler (APScheduler)
│   ├── Daily Fetch (6 AM)
│   └── Weekly Verify (Sunday 7 AM)
├── Scraper (Selenium + Chrome)
│   └── Hourly extraction via date dropdown (DD-MM-YYYY format)
└── SQLite Database
```

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI application entry point |
| `src/config.py` | Environment configuration |
| `src/api/routes.py` | API endpoint definitions |
| `src/scraper/extractor.py` | Thames Water data scraper (Selenium) |
| `src/scheduler/jobs.py` | Scheduled job definitions |
| `src/database/queries.py` | Database access layer |
| `static/index.html` | Dashboard HTML |
| `static/js/dashboard.js` | Dashboard JavaScript (includes cost calculations) |
| `static/css/styles.css` | Dashboard styling |
| `scripts/import_history.py` | Historical data import |
| `scripts/test_hourly.py` | Test hourly extraction |

## Dashboard Features

### Usage Cards
- **Latest Day**: Most recent day's usage (not "today" due to 3-day delay)
- **7-Day Average**: Rolling 7-day average usage
- **This Month**: Month-to-date total usage
- **Active Alerts**: Count of unacknowledged alerts

### Cost Cards (Green)
- **Daily Cost (Avg)**: Average daily cost based on 7-day usage
- **Month to Date**: Actual cost for days recorded this month
- **Projected Monthly**: Extrapolated full month cost
- **Annual Estimate**: Projected annual cost

### Charts
- **Daily Usage**: Bar chart with 30/90/365 day views and 800L threshold line
- **Hourly Breakdown**: Line chart for selected date (date picker)
- **Monthly Comparison**: Bar + line chart showing totals and daily averages

## Cost Calculation

Pricing from Thames Water Dec 2025 bill:

```javascript
// Rates per cubic metre (1000 litres)
Fresh water:    £2.4743/m³
Wastewater:     £1.5480/m³
Combined:       £4.0223/m³ = £0.0040223/litre

// Daily fixed charges (179-day billing period)
Fresh water:    £31.37 / 179 = £0.175/day
Wastewater:     £63.86 / 179 = £0.357/day
Total fixed:    £0.532/day

// Formula
Daily Cost = (Litres × £0.0040223) + £0.532
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/usage/summary` | GET | Usage statistics (supports `?days=7` param) |
| `/api/usage/daily` | GET | Daily usage records |
| `/api/usage/hourly` | GET | Hourly breakdown (supports `?date=YYYY-MM-DD`) |
| `/api/usage/monthly` | GET | Monthly aggregates |
| `/api/alerts` | GET | Alert history |
| `/api/sync/trigger` | POST | Manual sync (API key required) |

## Environment Variables

Required:
- `THAMES_WATER_EMAIL` - Thames Water login
- `THAMES_WATER_PASSWORD` - Thames Water password
- `THAMES_WATER_API_KEY` - API authentication key

Optional:
- `SPIKE_THRESHOLD` - Alert threshold (default: 800L)
- `NOTIFICATION_EMAIL` - Email for alerts
- `SMTP_*` - SMTP configuration for notifications

## Development

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn src.main:app --reload --port 8096

# Import historical data
uv run python scripts/import_history.py ../integrations/thames-water/full_history.csv

# Run backfill for specific month
uv run python scripts/backfill.py Dec-2025

# Test hourly extraction
uv run python scripts/test_hourly.py
```

## Deployment

Docker container on the **Hostinger VPS** at `~/apps/thames-water-service` (ZeroTier only,
`gavin@192.168.195.51`), deployed from branch **`prod`** — this worktree, `services/thames-water-prod`,
which matches GitHub `main`. The VPS copy is **not a git checkout**, so `git pull` there does nothing:
the tree is shipped by tar over ssh (BSD rsync silently skips updates), leaving `data/`, `logs/` and
`.env` in place.

```bash
cd /Volumes/DockSSD/projects/life/services/thames-water-prod
tar --exclude=.git --exclude=.venv --exclude='__pycache__' --exclude=data --exclude=logs --exclude=.env --exclude='*.bak*' -cf - . \
  | ssh gavin@192.168.195.51 'cd ~/apps/thames-water-service && tar -xf -'
ssh gavin@192.168.195.51 'cd ~/apps/thames-water-service && docker compose up -d --build'
# gate: something only the new code produces, not a 200 from /health
curl -s -o /dev/null -w '%{http_code}\n' -A gavin-life-scripts/1.0 -X POST -H 'Content-Type: application/json' \
  -d '{"daily":[],"hourly":[]}' https://water.gavinslater.co.uk/api/ingest   # expect 401
```

**Since v2.0.0 (2026-09-25) this service runs no browser** — readings arrive from the `hands` service via
`POST /api/ingest`; see the README. The *Scraper Details* section below describes the superseded v1
Selenium design (tag `v1-selenium`). The Raspberry Pi deployment is gone. Current hosting record:
`life-vault/docs/services/personal/Thames Water Service.md`.

## Scraper Details (v1, superseded)

The scraper uses Selenium with headless Chrome to:
1. Log in to Thames Water account
2. Navigate to water usage page
3. Extract daily data from "Monthly (by days)" view
4. Extract hourly data from "Daily (by hours)" view

### Hourly Data Extraction
- Thames Water provides ~7 days of hourly data
- Data delay: ~3 days from current date
- Date dropdown uses DD-MM-YYYY format (e.g., "15-12-2025")
- Extracts 24 hourly records per day

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Fetch | 6:00 AM | Retrieve daily and hourly data with meter readings |
| Weekly Verify | Sunday 7:00 AM | Meter-based data quality verification |

## Data Extraction

### Daily Sync Workflow
1. Select "Monthly (by days)" dropdown
2. Select "Last 30 days" period
3. Extract latest daily record with meter reading
4. Select "Daily (by hours)" dropdown
5. Select latest available date
6. Extract 24 hourly records with meter readings

### Data Fields Captured
- **Daily**: date, usage_litres, meter_reading, is_estimated
- **Hourly**: date, hour, usage_litres, meter_reading

## Weekly Verification (Meter-Based)

The weekly verification uses meter readings for accurate data quality checks:

### Verification Approach
1. **PRIMARY**: Compare daily reported usage with meter reading change (should match within 1L)
2. **SECONDARY**: Calculate overnight gaps between days to explain discrepancies
3. **FALLBACK**: If no meter data, compare daily vs hourly sum (5% tolerance)

### Data Quality Insight: Overnight Boundary Allocation
Thames Water allocates overnight usage inconsistently between days:
- Daily figures may include usage from overnight gaps
- Hourly sum at hour 00 may include previous day's overnight usage
- **Meter readings are authoritative** - use meter change for accurate verification

Example discrepancy pattern:
```
Dec 15: Daily=708L, Meter Change=669L, Diff=39L (overnight gap to Dec 16)
Dec 16: Daily=502L, Meter Change=502L, Diff=0L (verified)
```

## Alerts

Alerts are created for:
- **Spike**: Daily usage exceeds 800L threshold
- **Verification Mismatch**: Daily doesn't match meter change (unexpected discrepancy)
- **Data Unavailable**: Thames Water has no data available for a date (useful for detecting update patterns)
- **Data Available**: Hourly data became available for a date that was previously unavailable

## Database Schema

### daily_usage
| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | Date (YYYY-MM-DD) |
| usage_litres | REAL | Daily usage in litres |
| meter_reading | REAL | End-of-day meter reading |
| is_estimated | BOOL | Whether reading is estimated |
| hourly_sum | REAL | Sum of hourly readings (for verification) |
| verified | BOOL | Whether data passed verification |

### hourly_usage
| Column | Type | Description |
|--------|------|-------------|
| date | TEXT | Date (YYYY-MM-DD) |
| hour | INT | Hour (0-23) |
| usage_litres | REAL | Hourly usage in litres |
| meter_reading | REAL | Cumulative meter reading at end of hour |

### alerts
- Alert history (type, date, message, acknowledged)

### sync_log
- Synchronization history (type, status, records, duration)

## Troubleshooting

### No hourly data for certain dates
- Check date dropdown format in Thames Water UI (should be DD-MM-YYYY)
- Run `scripts/test_hourly.py` to debug extraction
- View scraper logs for dropdown detection messages

### Cost calculations seem wrong
- Verify pricing constants in `static/js/dashboard.js`
- Check Thames Water bill for current rates (may change annually)
- Fixed charges are calculated per day, not per billing period
