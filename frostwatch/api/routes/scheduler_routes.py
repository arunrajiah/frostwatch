from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from frostwatch.api.models import SchedulerJob
from frostwatch.core.scheduler import get_jobs_info

router = APIRouter()


@router.get("/scheduler/jobs", response_model=list[SchedulerJob])
async def list_scheduler_jobs(request: Request) -> list[SchedulerJob]:
    scheduler = request.app.state.scheduler
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    jobs_info = get_jobs_info(scheduler)
    return [
        SchedulerJob(
            job_id=j["job_id"],
            name=j["name"],
            next_run_time=j["next_run_time"],
            trigger_description=j["trigger_description"],
        )
        for j in jobs_info
    ]


@router.post("/scheduler/trigger")
async def trigger_scheduler(request: Request) -> dict:
    scheduler = request.app.state.scheduler
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    from frostwatch.snowflake.client import SnowflakeClient
    from frostwatch.api.routes.sync import run_sync
    import asyncio

    config = request.app.state.config
    client = SnowflakeClient(config)

    asyncio.create_task(run_sync(config, client))
    return {"status": "triggered"}
