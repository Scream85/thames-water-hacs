"""Constants for the Thames Water Smart Meter integration."""

from datetime import timedelta

DOMAIN = "thames_water_meter"

CONF_SPIKE_THRESHOLD = "spike_threshold"

DEFAULT_SPIKE_THRESHOLD = 800  # litres/day, same default as the original service
UPDATE_INTERVAL = timedelta(hours=6)  # Thames Water data lags ~3 days anyway
# Checked against a real account on 2026-10-07: hourly data is served for at least 90
# days and nothing for 180 or 365. The 60 and 90 day windows ended a day earlier than
# the 30 day one, so the freshest window is kept short and the older history is fetched
# separately, once per start-up.
HOURLY_RECENT_DAYS = 30
HOURLY_BACKFILL_DAYS = 90
