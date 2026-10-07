# Thames Water Smart Meter for Home Assistant

Native port of `gavraq/thames-water-service`. The Selenium/Chrome scraper, FastAPI app,
SQLite, scheduler, dashboard and SMTP alerts are replaced by Home Assistant itself.
Login and data come from the [`thameswaterapi`](https://pypi.org/project/thameswaterapi/)
library (direct web API, no browser).

## Source repositories
This project builds on two others:
* [`gavraq/thames-water-service`](https://github.com/gavraq/thames-water-service) - the original
  Selenium scraper, API, dashboard and alerts that this integration replaces.
* [`jelmer/homeassistant-thameswater`](https://github.com/jelmer/homeassistant-thameswater) - the
  existing Home Assistant integration (Apache-2.0), by the author of the
  [`thameswaterapi`](https://pypi.org/project/thameswaterapi/) library used here. It is based on
  earlier work by AyrtonB. This one adds the spike sensor, 7-day average, month-to-date and cost
  sensors, and uses a single coordinator.

## Install
### HACS (recommended)
1. HACS -> three dots -> **Custom repositories** -> add
   `https://github.com/Scream85/thames-water-hacs`, category **Integration**.
2. Download **Thames Water Smart Meter**, restart Home Assistant.
3. Settings -> Devices & services -> Add integration -> Thames Water Smart Meter.

### Manual
1. Copy `custom_components/thames_water_meter/` into your HA `config/custom_components/`
   (or add this folder as a HACS custom repository).
2. Restart Home Assistant (requires 2025.8+).
3. Settings -> Devices & services -> Add integration -> **Thames Water Smart Meter**.
4. Enter your Thames Water email and password.

## Running alongside other Thames Water integrations
The domain is `thames_water_meter`, so this can be installed next to
[`jelmer/homeassistant-thameswater`](https://github.com/jelmer/homeassistant-thameswater)
(domain `thames_water`). Entities and statistics are separate, and each integration logs in on
its own.

### Upgrading from 0.1.x (domain `thames_water`)
The domain changed in 0.2.0, so Home Assistant sees a different integration:
1. Delete the old **Thames Water Smart Meter** entry, then remove the old
   `config/custom_components/thames_water/` folder.
2. Install this version and add the integration again.
3. Pick the new statistic (`thames_water_meter:<meter>_water_consumption`) in the Energy
   dashboard. The old statistic keeps its history under its old name and can be left in place.

## What you get
| Entity | Notes |
|---|---|
| Latest day usage | litres; attribute `date` |
| 7-day average usage | litres/day |
| Month-to-date usage | litres |
| Meter reading | litres; attribute `statistic_id` |
| Latest day cost / Month-to-date cost | GBP, uses Thames Water's published tariff + daily standing charge |
| Usage spike | problem binary sensor, on when latest day > threshold (Configure -> default 800 L) |

## Energy dashboard (water)
Thames Water data is ~3 days old, so the integration imports **hourly long-term statistics at
their real timestamps** instead of relying on sensor states. In Settings -> Dashboards -> Energy
-> Water consumption -> Add, pick the statistic named
**"Thames Water <meter> consumption"** (not the sensors). Re-imports are idempotent.

## Alerts
Replace the old email alerts with an automation on the `Usage spike` binary sensor turning on,
calling any `notify.*` action.

## Known limits / things to verify
* Only ~7 days of hourly data exist at Thames Water, so history before install can't be backfilled
  beyond that. Daily history from your old SQLite DB can't be imported as hourly statistics.
* Assumes the API's usage and meter-read values are litres (consistent with the original
  service). Check the `Meter reading` attribute `read_taken_at` and compare with your bill/meter.
* First meter on the default contract account is used.
* Not tested against a live HA instance in the build environment: install on a test instance
  first and watch Settings -> System -> Logs for `thames_water_meter`.
