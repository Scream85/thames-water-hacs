"""APScheduler configuration and management."""

import uuid

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
    from src.scheduler.jobs import weekly_verification_job

    # Daily fetch at DAILY_FETCH_HOUR:DAILY_FETCH_MINUTE (06:00 UTC).
    #
    # This ran hourly from ~Dec 2024 as a "temporary" one-week investigation into
    # Thames Water data availability, and was never reverted. The cost: a full
    # Selenium/Chromium login every hour on a 2-core VPS, each blocking the
    # FastAPI event loop for ~110s, so the service stopped answering even its own
    # healthcheck for roughly 44 minutes a day. That window sat on the top of the
    # hour and collided with the 08:00 UTC doctor run, which reported the service
    # unreachable while it was merely blocked. Reverted 2026-09-11.
    #
    # Thames Water publishes once a day with a ~3-day lag, so hourly scraping
    # could not add anything once the investigation was over.
    if settings.scraper_mode == "selenium":
        from src.scheduler.jobs import daily_hourly_fetch_job

        scheduler.add_job(
            daily_hourly_fetch_job,
            CronTrigger(
                hour=settings.daily_fetch_hour,
                minute=settings.daily_fetch_minute,
            ),
            id="daily_hourly_fetch",
            name="Fetch previous day hourly data",
            replace_existing=True,
            misfire_grace_time=1800,
        )
        logger.warning(
            "Scheduled deprecated Selenium fetch at %02d:%02d",
            settings.daily_fetch_hour,
            settings.daily_fetch_minute,
        )
    else:
        logger.info("SCRAPER_MODE=external; Selenium fetch job is disabled")

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
    from src.scheduler.jobs import weekly_verification_job

    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Triggering manual job: {job_type}", extra={"job_id": job_id})

    if (
        job_type in {"daily", "hourly", "backfill"}
        and get_settings().scraper_mode != "selenium"
    ):
        raise ValueError(f"{job_type} job is disabled in external scraper mode")

    if job_type == "daily":
        # Run daily fetch immediately
        from src.scheduler.jobs import daily_hourly_fetch_job

        await daily_hourly_fetch_job()
    elif job_type == "hourly" and date:
        # Run hourly fetch for specific date
        from src.scheduler.jobs import fetch_hourly_for_date
        await fetch_hourly_for_date(date)
    elif job_type == "backfill":
        from src.scheduler.jobs import backfill_job

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
