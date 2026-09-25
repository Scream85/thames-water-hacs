from __future__ import annotations

import src.scheduler.manager as manager


async def test_external_mode_registers_verification_but_no_scrape_job():
    manager._scheduler = None
    try:
        await manager.start_scheduler()
        job_ids = {job.id for job in manager.get_scheduler().get_jobs()}
        assert job_ids == {"weekly_verification"}
    finally:
        await manager.stop_scheduler()
        manager._scheduler = None
