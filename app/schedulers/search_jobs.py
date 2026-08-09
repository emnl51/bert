from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..search_job_service import run_search_job
from ..search_job_store import ensure_search_job_schema, list_all_search_jobs

search_scheduler = AsyncIOScheduler(timezone=settings.timezone)


def build_search_job_trigger(search_job: dict):
    frequency = search_job.get("frequency", "weekly")
    if frequency == "disabled":
        return None
    if frequency == "interval":
        return IntervalTrigger(
            hours=max(1, int(search_job.get("interval_hours") or 12)),
            timezone=settings.timezone,
        )
    if frequency == "daily":
        return CronTrigger(
            hour=int(search_job.get("hour") or 0),
            minute=int(search_job.get("minute") or 0),
            timezone=settings.timezone,
        )
    return CronTrigger(
        day_of_week=search_job.get("day_of_week", "mon"),
        hour=int(search_job.get("hour") or 0),
        minute=int(search_job.get("minute") or 0),
        timezone=settings.timezone,
    )


def reschedule_search_jobs() -> None:
    ensure_search_job_schema()
    search_scheduler.remove_all_jobs()
    for search_job in list_all_search_jobs(mask_secrets=False):
        if not search_job["enabled"]:
            continue
        trigger = build_search_job_trigger(search_job)
        if trigger:
            search_scheduler.add_job(
                run_search_job,
                trigger,
                args=[search_job["id"]],
                id=f"search_job_{search_job['id']}",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
