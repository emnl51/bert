from contextlib import asynccontextmanager
from typing import Any
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import main as legacy
from .db import list_sources
from .profile_store import list_profiles
from .search_job_service import run_search_job
from .search_job_store import (
    delete_search_job,
    ensure_search_job_schema,
    get_search_job,
    list_search_job_runs,
    list_search_jobs,
    save_search_job,
)
from .security import require_admin
from .schedulers.search_jobs import reschedule_search_jobs, search_scheduler

app = legacy.app


_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def v10_lifespan(application):
    async with _original_lifespan(application):
        ensure_search_job_schema()
        # v10 Search Jobs replace the legacy single scheduled search to avoid duplicate notifications.
        if legacy.scheduler.get_job(legacy.JOB_ID):
            legacy.scheduler.remove_job(legacy.JOB_ID)
        reschedule_search_jobs()
        search_scheduler.start()
        yield
        search_scheduler.shutdown(wait=False)


app.router.lifespan_context = v10_lifespan
app.version = "10.0.0"


class SearchJobPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    profile_id: int
    target_location: str = "Berlin"
    location_terms: list[str] = []
    source_ids: list[int] = []
    frequency: str = "weekly"
    day_of_week: str = "mon"
    hour: int = Field(8, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    interval_hours: int = Field(12, ge=1, le=168)
    min_score_override: int | None = Field(default=None, ge=0, le=100)
    min_language_score_override: int | None = Field(default=None, ge=0, le=100)
    max_results: int = Field(20, ge=1, le=100)
    notify_telegram: bool = False
    notify_email: bool = False
    notification: dict[str, Any] = {}
    secrets: dict[str, str] = {}


@app.get("/search-job-ui.js")
def search_job_ui(_: str = Depends(require_admin)):
    from pathlib import Path

    return Response(Path("app/search-job-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/api/search-jobs")
def api_search_jobs(_: str = Depends(require_admin)):
    jobs = list_search_jobs(mask_secrets=True)
    next_runs = {
        j.id.replace("search_job_", ""): j.next_run_time.isoformat() if j.next_run_time else None
        for j in search_scheduler.get_jobs()
    }
    for sj in jobs:
        sj["next_run"] = next_runs.get(str(sj["id"]))
    return {"search_jobs": jobs, "profiles": list_profiles(), "sources": list_sources(mask_secrets=True)}


@app.post("/api/search-jobs")
def create_search_job(payload: SearchJobPayload, _: str = Depends(require_admin)):
    if payload.frequency not in ("disabled", "interval", "daily", "weekly"):
        raise HTTPException(400, "Invalid frequency")
    try:
        job_id = save_search_job(payload.model_dump())
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    reschedule_search_jobs()
    return {"ok": True, "id": job_id}


@app.put("/api/search-jobs/{job_id}")
def update_search_job(job_id: int, payload: SearchJobPayload, _: str = Depends(require_admin)):
    if not get_search_job(job_id, True):
        raise HTTPException(404, "Search job not found")
    try:
        save_search_job(payload.model_dump(), job_id=job_id)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    reschedule_search_jobs()
    return {"ok": True}


@app.delete("/api/search-jobs/{job_id}")
def remove_search_job(job_id: int, _: str = Depends(require_admin)):
    delete_search_job(job_id)
    reschedule_search_jobs()
    return {"ok": True}


@app.post("/api/search-jobs/{job_id}/run")
async def run_search_job_now(job_id: int, _: str = Depends(require_admin)):
    if not get_search_job(job_id, False):
        raise HTTPException(404, "Search job not found")
    try:
        return {"ok": True, **await run_search_job(job_id)}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/search-jobs/{job_id}/runs")
def search_job_runs(job_id: int, _: str = Depends(require_admin)):
    return {"runs": list_search_job_runs(job_id, 100)}


@app.get("/api/search-job-runs")
def all_search_job_runs(_: str = Depends(require_admin)):
    return {"runs": list_search_job_runs(None, 100)}


@app.get("/api/v10-health")
def v10_health(_: str = Depends(require_admin)):
    return {
        "status": "ok",
        "version": "10.0.0",
        "search_jobs": len(list_search_jobs()),
        "scheduled_jobs": len(search_scheduler.get_jobs()),
    }
