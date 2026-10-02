"""API route definitions."""

import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.middleware import verify_api_key, verify_ingest_key
from src.api.schemas import (
    AcknowledgeAlertResponse,
    AlertItem,
    AlertsResponse,
    DailyUsageItem,
    DailyUsageResponse,
    HealthResponse,
    HourlyUsageItem,
    HourlyUsageResponse,
    IngestRequest,
    IngestResponse,
    MonthlyUsageItem,
    MonthlyUsageResponse,
    PaginationInfo,
    SyncStatusResponse,
    TriggerSyncRequest,
    TriggerSyncResponse,
    UsageSummaryResponse,
)
from src.database.connection import get_database
from src.database.models import DailyUsage, HourlyUsage, SyncLog
from src.database.queries import (
    acknowledge_alert,
    create_sync_log,
    get_alerts,
    get_daily_usage,
    get_daily_usage_count,
    get_hourly_sum,
    get_hourly_usage,
    get_last_sync,
    get_monthly_usage,
    get_recent_sync_errors,
    get_usage_summary,
    insert_daily_usage,
    insert_hourly_usage,
)
from src.ingest.validation import validate_daily_usage, validate_hourly_usage
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/api/ingest",
    response_model=IngestResponse,
    tags=["Ingest"],
    dependencies=[Depends(verify_ingest_key)],
)
async def ingest_from_hands(payload: IngestRequest) -> IngestResponse:
    """Validate and upsert consumption collected by the Hands browser adapter."""
    started = time.monotonic()
    daily = [DailyUsage(**item.model_dump(), source="hands") for item in payload.daily]
    hourly = [HourlyUsage(**item.model_dump(), source="hands") for item in payload.hourly]

    if any(not validate_daily_usage(item) for item in daily):
        raise HTTPException(status_code=422, detail="Invalid daily usage record")
    if any(not validate_hourly_usage(item) for item in hourly):
        raise HTTPException(status_code=422, detail="Invalid hourly usage record")

    from src.scheduler.jobs import check_for_spike

    for item in daily:
        await insert_daily_usage(item)
        await check_for_spike(item)
    for item in hourly:
        await insert_hourly_usage(item)

    dates = [item.date for item in daily] + [item.date for item in hourly]
    total = len(daily) + len(hourly)
    await create_sync_log(
        SyncLog(
            sync_type="ingest",
            source="hands",
            sync_time=datetime.now(timezone.utc),
            status="success",
            records_fetched=total,
            records_stored=total,
            date_range_start=min(dates) if dates else None,
            date_range_end=max(dates) if dates else None,
            duration_seconds=time.monotonic() - started,
        )
    )
    return IngestResponse(daily=len(daily), hourly=len(hourly))


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Service health check endpoint."""
    db = get_database()

    # Check database connectivity
    db_healthy = False
    try:
        await db.fetch_one("SELECT 1")
        db_healthy = True
    except Exception:
        pass

    # Get last sync times
    last_daily = await get_last_sync("daily")
    last_hourly = await get_last_sync("hourly")

    status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    if not db_healthy:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc),
        version="2.1.0",
        services={
            "database": db_healthy,
            "scraper": True,  # Assume scraper is available
            "scheduler": True,  # Assume scheduler is running
        },
        last_sync={
            "daily": last_daily["sync_time"] if last_daily else None,
            "hourly": last_hourly["sync_time"] if last_hourly else None,
        },
    )


# =============================================================================
# Usage Endpoints
# =============================================================================


@router.get(
    "/api/usage/summary",
    response_model=UsageSummaryResponse,
    tags=["Usage"],
)
async def get_usage_summary_endpoint(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to summarize"),
) -> UsageSummaryResponse:
    """Get usage summary statistics."""
    try:
        summary = await get_usage_summary(days)

        return UsageSummaryResponse(
            success=True,
            data={
                "period": summary.period,
                "total_litres": summary.total_litres,
                "average_daily": round(summary.average_daily, 1),
                "max_daily": summary.max_daily,
                "min_daily": summary.min_daily,
                "days_recorded": summary.days_recorded,
                "days_above_threshold": summary.days_above_threshold,
                "trend": summary.trend,
                "date_range": summary.date_range,
            },
            message=f"Usage summary for {days} days",
        )

    except Exception as e:
        logger.error(f"Error getting usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/usage/daily",
    response_model=DailyUsageResponse,
    tags=["Usage"],
)
async def get_daily_usage_endpoint(
    start_date: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum records"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> DailyUsageResponse:
    """Get daily usage records."""
    try:
        records = await get_daily_usage(start_date, end_date, limit, offset)
        total = await get_daily_usage_count(start_date, end_date)

        data = [
            DailyUsageItem(
                date=r["date"],
                usage_litres=r["usage_litres"],
                meter_reading=r["meter_reading"],
                is_estimated=bool(r["is_estimated"]),
                verified=bool(r["verified"]),
            )
            for r in records
        ]

        return DailyUsageResponse(
            success=True,
            data=data,
            pagination=PaginationInfo(total=total, limit=limit, offset=offset),
            message=f"Retrieved {len(data)} daily records",
        )

    except Exception as e:
        logger.error(f"Error getting daily usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/usage/hourly",
    response_model=HourlyUsageResponse,
    tags=["Usage"],
)
async def get_hourly_usage_endpoint(
    date: str = Query(description="Date to get hourly data for (YYYY-MM-DD)"),
) -> HourlyUsageResponse:
    """Get hourly usage breakdown for a specific date."""
    try:
        records = await get_hourly_usage(date)
        daily_total = await get_hourly_sum(date)

        hourly_data = [
            HourlyUsageItem(hour=r["hour"], usage_litres=r["usage_litres"])
            for r in records
        ]

        from src.api.schemas import HourlyUsageData
        return HourlyUsageResponse(
            success=True,
            data=HourlyUsageData(
                date=date,
                hourly=hourly_data,
                daily_total=daily_total or 0.0,
            ),
            message=f"Hourly data for {date}",
        )

    except Exception as e:
        logger.error(f"Error getting hourly usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/api/usage/monthly",
    response_model=MonthlyUsageResponse,
    tags=["Usage"],
)
async def get_monthly_usage_endpoint(
    year: int | None = Query(default=None, description="Filter by year"),
) -> MonthlyUsageResponse:
    """Get monthly usage aggregates."""
    try:
        records = await get_monthly_usage(year)

        data = [
            MonthlyUsageItem(
                month=r.month,
                total_litres=r.total_litres,
                average_daily=round(r.average_daily, 1),
                days_recorded=r.days_recorded,
                max_daily=r.max_daily,
                min_daily=r.min_daily,
            )
            for r in records
        ]

        return MonthlyUsageResponse(
            success=True,
            data=data,
            message=f"Retrieved {len(data)} monthly aggregates",
        )

    except Exception as e:
        logger.error(f"Error getting monthly usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Alerts Endpoints
# =============================================================================


@router.get(
    "/api/alerts",
    response_model=AlertsResponse,
    tags=["Alerts"],
)
async def get_alerts_endpoint(
    status: Literal["all", "unacknowledged", "acknowledged"] = Query(
        default="all", description="Filter by acknowledgement status"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum records"),
) -> AlertsResponse:
    """Get alert history."""
    try:
        records = await get_alerts(status, limit)

        data = [
            AlertItem(
                id=r["id"],
                alert_type=r["alert_type"],
                alert_date=r["alert_date"],
                message=r["message"],
                value=r["value"],
                threshold=r["threshold"],
                notified=bool(r["notified"]),
                acknowledged=bool(r["acknowledged"]),
                created_at=r["created_at"],
            )
            for r in records
        ]

        return AlertsResponse(
            success=True,
            data=data,
            message=f"Retrieved {len(data)} alerts",
        )

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/alerts/{alert_id}/acknowledge",
    response_model=AcknowledgeAlertResponse,
    tags=["Alerts"],
    dependencies=[Depends(verify_api_key)],
)
async def acknowledge_alert_endpoint(alert_id: int) -> AcknowledgeAlertResponse:
    """Acknowledge an alert."""
    try:
        await acknowledge_alert(alert_id)

        return AcknowledgeAlertResponse(
            success=True,
            message=f"Alert {alert_id} acknowledged",
        )

    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Sync Endpoints (Protected)
# =============================================================================


@router.get(
    "/api/sync/status",
    response_model=SyncStatusResponse,
    tags=["Sync"],
)
async def get_sync_status() -> SyncStatusResponse:
    """Get synchronization status."""
    try:
        last_daily = await get_last_sync("daily")
        last_weekly = await get_last_sync("weekly_verify")
        last_ingest = await get_last_sync("ingest")
        recent_errors = await get_recent_sync_errors(5)

        return SyncStatusResponse(
            success=True,
            data={
                "last_daily_sync": last_daily["sync_time"] if last_daily else None,
                "last_daily_status": last_daily["status"] if last_daily else None,
                "last_weekly_verify": last_weekly["sync_time"] if last_weekly else None,
                "last_ingest_sync": last_ingest["sync_time"] if last_ingest else None,
                "last_ingest_status": last_ingest["status"] if last_ingest else None,
                "last_ingest_source": last_ingest["source"] if last_ingest else None,
                "last_ingest_range_end": last_ingest["date_range_end"] if last_ingest else None,
                "pending_jobs": 0,  # Could be populated from scheduler
                "recent_errors": [
                    {
                        "time": e["sync_time"],
                        "type": e["sync_type"],
                        "message": e["error_message"],
                    }
                    for e in recent_errors
                ],
            },
            message="Sync status retrieved",
        )

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/sync/trigger",
    response_model=TriggerSyncResponse,
    tags=["Sync"],
    dependencies=[Depends(verify_api_key)],
)
async def trigger_sync(request: TriggerSyncRequest) -> TriggerSyncResponse:
    """Trigger a manual sync job."""
    try:
        # Import scheduler to trigger job
        from src.scheduler.manager import trigger_job

        job_id = await trigger_job(request.sync_type, request.date)

        return TriggerSyncResponse(
            success=True,
            message=f"Triggered {request.sync_type} sync",
            job_id=job_id,
        )

    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))
