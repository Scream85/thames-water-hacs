"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Response Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: datetime
    version: str = "1.0.0"
    services: dict[str, bool]
    last_sync: dict[str, str | None] | None = None


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    total: int
    limit: int
    offset: int


class UsageSummaryResponse(BaseModel):
    """Usage summary response."""

    success: bool = True
    data: dict
    message: str = "Usage summary retrieved"


class DailyUsageItem(BaseModel):
    """Single daily usage record."""

    date: str
    usage_litres: float
    meter_reading: float | None = None
    is_estimated: bool = False
    verified: bool = False


class DailyUsageResponse(BaseModel):
    """Daily usage list response."""

    success: bool = True
    data: list[DailyUsageItem]
    pagination: PaginationInfo
    message: str = "Daily usage data retrieved"


class HourlyUsageItem(BaseModel):
    """Single hourly usage record."""

    hour: int
    usage_litres: float


class HourlyUsageData(BaseModel):
    """Hourly usage data structure."""

    date: str
    hourly: list[HourlyUsageItem]
    daily_total: float


class HourlyUsageResponse(BaseModel):
    """Hourly usage response."""

    success: bool = True
    data: HourlyUsageData
    message: str = "Hourly usage data retrieved"


class MonthlyUsageItem(BaseModel):
    """Monthly usage aggregate."""

    month: str
    total_litres: float
    average_daily: float
    days_recorded: int
    max_daily: float | None = None
    min_daily: float | None = None


class MonthlyUsageResponse(BaseModel):
    """Monthly usage response."""

    success: bool = True
    data: list[MonthlyUsageItem]
    message: str = "Monthly usage data retrieved"


class AlertItem(BaseModel):
    """Single alert record."""

    id: int
    alert_type: str
    alert_date: str
    message: str
    value: float | None = None
    threshold: float | None = None
    notified: bool = False
    acknowledged: bool = False
    created_at: str | None = None


class AlertsResponse(BaseModel):
    """Alerts list response."""

    success: bool = True
    data: list[AlertItem]
    message: str = "Alerts retrieved"


class SyncStatusResponse(BaseModel):
    """Sync status response."""

    success: bool = True
    data: dict
    message: str = "Sync status retrieved"


class TriggerSyncResponse(BaseModel):
    """Trigger sync response."""

    success: bool = True
    message: str
    job_id: str | None = None


class AcknowledgeAlertResponse(BaseModel):
    """Acknowledge alert response."""

    success: bool = True
    message: str = "Alert acknowledged"


class IngestResponse(BaseModel):
    """Counts returned after a Hands ingestion."""

    daily: int
    hourly: int


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: str | None = None


# =============================================================================
# Request Models
# =============================================================================


class TriggerSyncRequest(BaseModel):
    """Request to trigger a sync job."""

    sync_type: Literal["daily", "hourly", "backfill"] = Field(
        description="Type of sync to trigger"
    )
    date: str | None = Field(
        default=None,
        description="Specific date for hourly sync (YYYY-MM-DD)"
    )


class IngestDailyItem(BaseModel):
    """Daily reading sent by the Hands Thames Water adapter."""

    date: str
    usage_litres: float
    meter_reading: float | None = None
    is_estimated: bool = False


class IngestHourlyItem(BaseModel):
    """Hourly reading sent by the Hands Thames Water adapter."""

    date: str
    hour: int = Field(ge=0, le=23)
    usage_litres: float
    meter_reading: float | None = None
    is_estimated: bool = False


class IngestRequest(BaseModel):
    """Validated boundary for externally collected consumption data."""

    daily: list[IngestDailyItem]
    hourly: list[IngestHourlyItem]
    source: Literal["hands"]
