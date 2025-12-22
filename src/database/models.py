"""Database models and Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DailyUsage(BaseModel):
    """Daily water usage record."""

    id: int | None = None
    date: str = Field(description="Date in YYYY-MM-DD format")
    usage_litres: float = Field(description="Total daily usage in litres")
    meter_reading: float | None = Field(default=None, description="End-of-day meter reading")
    is_estimated: bool = Field(default=False, description="Whether data is estimated")
    hourly_sum: float | None = Field(default=None, description="Sum of hourly data")
    verified: bool = Field(default=False, description="Whether hourly sum matches daily")
    source: str = Field(default="scraper", description="Data source")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HourlyUsage(BaseModel):
    """Hourly water usage record."""

    id: int | None = None
    date: str = Field(description="Date in YYYY-MM-DD format")
    hour: int = Field(ge=0, le=23, description="Hour of day (0-23)")
    usage_litres: float = Field(description="Hourly usage in litres")
    meter_reading: float | None = Field(default=None, description="Meter reading at hour end")
    is_estimated: bool = Field(default=False, description="Whether data is estimated")
    source: str = Field(default="scraper", description="Data source")
    created_at: datetime | None = None


class SyncLog(BaseModel):
    """Data synchronization log entry."""

    id: int | None = None
    sync_type: Literal["daily", "hourly", "weekly_verify", "backfill"]
    sync_time: datetime
    status: Literal["success", "error", "partial"]
    records_fetched: int = 0
    records_stored: int = 0
    date_range_start: str | None = None
    date_range_end: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    duration_seconds: float | None = None
    created_at: datetime | None = None


class Alert(BaseModel):
    """Alert record."""

    id: int | None = None
    alert_type: Literal["spike", "sync_error", "verification_mismatch", "data_unavailable", "data_available"]
    alert_date: str = Field(description="Date in YYYY-MM-DD format")
    message: str
    value: float | None = Field(default=None, description="Value that triggered alert")
    threshold: float | None = Field(default=None, description="Threshold exceeded")
    notified: bool = False
    notified_at: datetime | None = None
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    created_at: datetime | None = None


class UsageSummary(BaseModel):
    """Usage summary statistics."""

    period: str = Field(description="Summary period description")
    total_litres: float
    average_daily: float
    max_daily: float
    min_daily: float
    days_recorded: int
    days_above_threshold: int = 0
    trend: Literal["rising", "falling", "stable"] = "stable"
    date_range: dict[str, str] | None = None


class MonthlyUsage(BaseModel):
    """Monthly usage aggregate."""

    month: str = Field(description="Month in YYYY-MM format")
    total_litres: float
    average_daily: float
    days_recorded: int
    max_daily: float | None = None
    min_daily: float | None = None
