"""APScheduler configuration and management."""

import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler with configured jobs."""
    settings = get_settings()
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("Scheduler already running")
        return

    # Import jobs here to avoid circular imports
    from src.scheduler.jobs import (
        daily_hourly_fetch_job,
        weekly_verification_job,
    )

    # TEMPORARY: Run hourly to investigate Thames Water data availability patterns
    # TODO: Revert to daily after ~1 week of data collection (around 2025-01-01)
    # Original: CronTrigger(hour=settings.daily_fetch_hour, minute=settings.daily_fetch_minute)
    scheduler.add_job(
        daily_hourly_fetch_job,
        CronTrigger(
            minute=0,  # Run at the top of every hour
        ),
        id="daily_hourly_fetch",
        name="Fetch previous day hourly data",
        replace_existing=True,
        misfire_grace_time=1800,  # 30 min grace period for hourly runs
    )
    logger.info("Scheduled hourly fetch (TEMPORARY - investigating data availability)")

    # Weekly job: Verify daily totals against hourly sums
    scheduler.add_job(
        weekly_verification_job,
        CronTrigger(
            day_of_week=settings.weekly_verify_day,
            hour=settings.weekly_verify_hour,
            minute=0,
        ),
        id="weekly_verification",
        name="Weekly data verification",
        replace_existing=True,
        misfire_grace_time=7200,  # 2 hour grace period
    )
    logger.info(
        f"Scheduled weekly verification on {settings.weekly_verify_day} at {settings.weekly_verify_hour:02d}:00"
    )

    scheduler.start()
    logger.info("Scheduler started")


async def stop_scheduler() -> None:
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


async def trigger_job(job_type: str, date: str | None = None) -> str:
    """
    Trigger a job manually.

    Args:
        job_type: Type of job ('daily', 'hourly', 'backfill')
        date: Optional date for specific date sync

    Returns:
        Job ID
    """
    from src.scheduler.jobs import (
        daily_hourly_fetch_job,
        weekly_verification_job,
        backfill_job,
    )

    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Triggering manual job: {job_type}", extra={"job_id": job_id})

    if job_type == "daily":
        # Run daily fetch immediately
        await daily_hourly_fetch_job()
    elif job_type == "hourly" and date:
        # Run hourly fetch for specific date
        from src.scheduler.jobs import fetch_hourly_for_date
        await fetch_hourly_for_date(date)
    elif job_type == "backfill":
        await backfill_job()
    elif job_type == "weekly_verify":
        await weekly_verification_job()
    else:
        raise ValueError(f"Unknown job type: {job_type}")

    return job_id


def get_job_status() -> dict:
    """Get status of scheduled jobs."""
    scheduler = get_scheduler()

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }
