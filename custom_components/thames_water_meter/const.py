"""Constants for the Thames Water Smart Meter integration."""

from datetime import timedelta

DOMAIN = "thames_water_meter"

CONF_SPIKE_THRESHOLD = "spike_threshold"

DEFAULT_SPIKE_THRESHOLD = 800  # litres/day, same default as the original service
UPDATE_INTERVAL = timedelta(hours=6)  # Thames Water data lags ~3 days anyway
HOURLY_LOOKBACK_DAYS = 7  # Thames Water only serves ~7 days of hourly data
