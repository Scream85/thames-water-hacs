# Ingest from Hands

## What

The production Thames Water service accepts consumption collected by the separate Hands browser
service. `POST /api/ingest` takes daily and hourly readings authenticated with `X-Ingest-Key`.
This replaces Chrome/Selenium inside the water-service container while leaving the dashboard,
alerts, verification, and SQLite history here.

```json
{
  "daily": [{
    "date": "2026-09-21",
    "usage_litres": 420.0,
    "meter_reading": 123456.0,
    "is_estimated": false
  }],
  "hourly": [{
    "date": "2026-09-21",
    "hour": 7,
    "usage_litres": 18.5,
    "meter_reading": 123000.0,
    "is_estimated": false
  }],
  "source": "hands"
}
```

The response reports accepted counts: `{"daily": 1, "hourly": 1}`.

## How

- The endpoint fails closed when `INGEST_API_KEY` is unset and rejects missing or incorrect keys.
- Existing parser validators check date formats, hour ranges, and non-negative consumption.
- Existing daily and hourly upserts make repeat delivery idempotent by date and date/hour.
- Every successful delivery adds an `ingest` sync log with `source="hands"`.
- Daily records pass through the existing spike check and its alert de-duplication.
- The only scheduled job is the weekly database verification; v2.1.0 removed the Selenium
  collector and the `SCRAPER_MODE` switch.

## Implemented and deployment notes

This is implemented on the repository's `prod` branch. Production now deploys from that branch,
not the separate development line.

Set these values in the deployment `.env` before rebuilding:

```dotenv
INGEST_API_KEY=<same secret used as WATER_INGEST_KEY by Hands>
```

Keep `THAMES_WATER_API_KEY` for the existing administrative endpoints. External mode does not
need Thames Water login credentials in this container. The slim image contains no Chrome,
chromedriver, Selenium, VNC, or browser ports.
