# Thames Water Monitoring Service

Automated water usage monitoring service with data collection, REST API, dashboard, and cost tracking.

## Features

- **Automated Data Collection**: Daily and hourly usage delivered by the Hands browser service
- **Meter Reading Capture**: Cumulative meter readings stored with hourly data
- **REST API**: Query usage data, summaries, and alerts
- **Dashboard**: Visual usage trends with Chart.js
- **Cost Tracking**: Real-time cost calculations based on Thames Water rates
- **Spike Alerts**: Email notifications when usage exceeds threshold (800L)
- **Meter-Based Verification**: Weekly verification using meter readings for accurate data quality checks

## Dashboard

The dashboard at https://water.gavinslater.co.uk displays:

### Usage Statistics
- **Latest Day**: Most recent available day's usage (~3 day delay)
- **7-Day Average**: Rolling average consumption
- **This Month**: Month-to-date total
- **Active Alerts**: Unacknowledged spike alerts

### Cost Estimates (Green Cards)
- **Daily Cost**: Average daily cost including fixed charges
- **Month to Date**: Actual cost for recorded days
- **Projected Monthly**: Full month estimate
- **Annual Estimate**: Yearly projection

### Charts
- Daily usage (30/90/365 day views) with 800L threshold
- Hourly breakdown per selected date
- Monthly comparison with averages

## Quick Start

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Set INGEST_API_KEY, SCRAPER_MODE=external, and the existing admin API key

# Run locally
uv run uvicorn src.main:app --reload --port 8096

# Or with Docker
docker-compose up -d
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/usage/summary?days=7` | GET | Summary statistics |
| `/api/usage/daily` | GET | Daily usage data |
| `/api/usage/hourly?date=YYYY-MM-DD` | GET | Hourly breakdown |
| `/api/usage/monthly` | GET | Monthly aggregates |
| `/api/alerts` | GET | Alert history |
| `/api/ingest` | POST | Hands daily/hourly ingest (`X-Ingest-Key`) |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `THAMES_WATER_API_KEY` | API authentication key | Required |
| `INGEST_API_KEY` | Separate Hands ingest key | Required |
| `SCRAPER_MODE` | `external` or deprecated `selenium` collection | external |
| `THAMES_WATER_EMAIL` | Login email for deprecated Selenium mode | None |
| `THAMES_WATER_PASSWORD` | Login password for deprecated Selenium mode | None |
| `SPIKE_THRESHOLD` | Usage threshold for alerts (litres) | 800 |
| `NOTIFICATION_EMAIL` | Email for alerts | gavin@slaters.uk.com |
| `PORT` | Service port | 8096 |

## Cost Calculation

Based on Thames Water Dec 2025 rates:

| Component | Rate |
|-----------|------|
| Fresh water | £2.4743/m³ |
| Wastewater | £1.5480/m³ |
| **Combined** | **£4.0223/m³** (£0.0040223/litre) |
| Daily fixed charge | £0.532/day |

Formula: `Daily Cost = (Litres × £0.0040223) + £0.532`

## Docker Deployment

The service is designed to run on a Raspberry Pi 5 with ARM64 architecture.

```bash
# Deploy
docker-compose up -d

# Rebuild after changes
docker-compose up -d --build

# View logs
docker-compose logs -f thames-water-service
```

Access via: https://water.gavinslater.co.uk

## How data arrives now (hands)

The Hands service owns the authenticated browser session. Its Thames Water adapter reads the
account's consumption JSON, validates daily and hourly records, and posts them to
`POST /api/ingest` with `X-Ingest-Key`. This service validates the records again, upserts them
into SQLite, creates spike alerts, and records a `source="hands"` sync log. Re-posting the same
date/hour updates the existing rows rather than duplicating them.

Production runs with `SCRAPER_MODE=external`, so APScheduler keeps the database-only weekly
verification job but does not register the Selenium collection job. See
[`docs/features/ingest-from-hands.md`](docs/features/ingest-from-hands.md) for the contract and
deployment notes.

### Legacy Selenium extractor (deprecated)

The in-process extractor is retained only for rollback via `SCRAPER_MODE=selenium`. It requires
the optional `selenium` dependency group and a separately supplied Chrome/chromedriver runtime;
neither is present in the slim production image.

## Data Notes

- **Data Delay**: Thames Water provides data with ~3 day delay
- **Hourly Data**: ~7 days of hourly data available at any time
- **Date Format**: Thames Water UI uses DD-MM-YYYY format for date selection
- **Meter Readings**: Cumulative meter readings captured with each hourly record
- **Data Quality**: Weekly verification compares daily usage against meter reading changes
- **Overnight Allocation**: Thames Water may allocate overnight usage inconsistently between days; meter readings are authoritative

## Development

```bash
# Test hourly data extraction
uv run python scripts/test_hourly.py

# Import historical CSV data
uv run python scripts/import_history.py path/to/history.csv

# Backfill specific month
uv run python scripts/backfill.py Dec-2025
```
