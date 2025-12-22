# Thames Water Monitoring Service

Automated water usage monitoring service for Thames Water smart meter customers. Collects daily and hourly usage data via web scraping, provides a REST API, visual dashboard, and email alerts for unusual consumption.

## Features

- **Automated Data Collection**: Daily and hourly usage retrieval via Selenium scraper
- **Meter Reading Capture**: Cumulative meter readings stored with hourly data
- **REST API**: Query usage data, summaries, and alerts programmatically
- **Dashboard**: Visual usage trends with Chart.js (daily, hourly, monthly views)
- **Cost Tracking**: Real-time cost calculations based on Thames Water rates
- **Spike Alerts**: Email notifications when usage exceeds configurable threshold
- **Meter-Based Verification**: Weekly verification using meter readings for accurate data quality

## Prerequisites

- Thames Water account with smart meter installed
- Python 3.11+ (or Docker)
- Chrome/Chromium (for Selenium scraping)

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/gavraq/thames-water-service.git
cd thames-water-service

# Install dependencies (using uv)
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your Thames Water credentials

# Run locally
uv run uvicorn src.main:app --reload --port 8096
```

### Docker Deployment

```bash
# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Deploy
docker-compose up -d

# View logs
docker-compose logs -f thames-water-service
```

The service is designed to run on a Raspberry Pi 5 (ARM64) but works on any Docker-compatible system.

## Dashboard

Access the dashboard at `http://localhost:8096` (or your configured domain).

### Usage Statistics
- **Latest Day**: Most recent available day's usage (~3 day delay from Thames Water)
- **7-Day Average**: Rolling average consumption
- **This Month**: Month-to-date total
- **Active Alerts**: Unacknowledged spike alerts

### Cost Estimates
- **Daily Cost**: Average daily cost including fixed charges
- **Month to Date**: Actual cost for recorded days
- **Projected Monthly**: Full month estimate
- **Annual Estimate**: Yearly projection

### Charts
- Daily usage (30/90/365 day views) with threshold line
- Hourly breakdown per selected date
- Monthly comparison with averages

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/api/usage/summary?days=7` | GET | Summary statistics |
| `/api/usage/daily` | GET | Daily usage data |
| `/api/usage/hourly?date=YYYY-MM-DD` | GET | Hourly breakdown |
| `/api/usage/monthly` | GET | Monthly aggregates |
| `/api/alerts` | GET | Alert history |
| `/api/sync/trigger` | POST | Manual sync (requires API key) |

Full API documentation available at `/docs` (Swagger UI).

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `THAMES_WATER_EMAIL` | Thames Water login email | Required |
| `THAMES_WATER_PASSWORD` | Thames Water login password | Required |
| `THAMES_WATER_API_KEY` | API authentication key | Required |
| `SPIKE_THRESHOLD` | Usage threshold for alerts (litres) | 800 |
| `NOTIFICATION_EMAIL` | Email for alerts | (none) |
| `SERVICE_URL` | Public URL for email links | http://localhost:8096 |
| `PORT` | Service port | 8096 |
| `SMTP_HOST` | SMTP server for notifications | (none) |
| `SMTP_PORT` | SMTP port | 587 |
| `SMTP_USERNAME` | SMTP username | (none) |
| `SMTP_PASSWORD` | SMTP password | (none) |

## Cost Calculation

Based on Thames Water December 2025 rates:

| Component | Rate |
|-----------|------|
| Fresh water | £2.4743/m³ |
| Wastewater | £1.5480/m³ |
| **Combined** | **£4.0223/m³** (£0.0040223/litre) |
| Daily fixed charge | £0.532/day |

Formula: `Daily Cost = (Litres × £0.0040223) + £0.532`

> **Note**: Rates may change. Check your Thames Water bill for current pricing.

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

## Architecture

```
FastAPI Application
├── API Endpoints (/api/*)
├── Dashboard (static HTML + Chart.js)
├── Scheduler (APScheduler)
│   ├── Daily Fetch (configurable time)
│   └── Weekly Verification
├── Scraper (Selenium + Chrome)
└── SQLite Database
```

## Tutorial

See [TUTORIAL.md](TUTORIAL.md) for a comprehensive walkthrough of the codebase, covering:
- Project structure and architecture
- Pydantic models and type safety
- Async database operations
- Selenium web scraping
- APScheduler configuration
- FastAPI endpoints
- Dashboard development
- Docker deployment

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by the need to understand an unexpectedly large water bill
- Built with [FastAPI](https://fastapi.tiangolo.com/), [Selenium](https://selenium.dev/), and [Chart.js](https://www.chartjs.org/)
