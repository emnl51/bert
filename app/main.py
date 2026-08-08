from contextlib import asynccontextmanager
import asyncio
from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from .config import settings
from .db import (
    application_stats, dashboard_stats, delete_keyword, delete_source, get_all_settings, get_source, init_db,
    list_applications, list_jobs, list_keywords, list_runs, list_sources, save_application, save_keyword,
    save_source, set_job_decision, set_setting,
)
from .notifier import test_email, test_telegram
from .providers import test_source
from .runtime import runtime_config
from .security import require_admin
from .service import run_search

scheduler = AsyncIOScheduler(timezone=settings.timezone)
templates = Jinja2Templates(directory='app/templates')
JOB_ID = 'scheduled_job_search'


def build_trigger(cfg: dict):
    frequency = cfg['schedule_frequency']
    if frequency == 'disabled':
        return None
    if frequency == 'interval':
        return IntervalTrigger(hours=max(1, cfg['schedule_interval_hours']), timezone=cfg['timezone'])
    if frequency == 'daily':
        return CronTrigger(hour=cfg['schedule_hour'], minute=cfg['schedule_minute'], timezone=cfg['timezone'])
    return CronTrigger(
        day_of_week=cfg['schedule_day'], hour=cfg['schedule_hour'], minute=cfg['schedule_minute'],
        timezone=cfg['timezone'],
    )


def reschedule() -> None:
    cfg = runtime_config()
    existing = scheduler.get_job(JOB_ID)
    if existing:
        scheduler.remove_job(JOB_ID)
    trigger = build_trigger(cfg)
    if trigger:
        scheduler.add_job(run_search, trigger, id=JOB_ID, replace_existing=True, max_instances=1, coalesce=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    reschedule()
    scheduler.start()
    if settings.run_on_start:
        asyncio.create_task(run_search())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version='3.0.0', lifespan=lifespan)


class AppSettingsPayload(BaseModel):
    target_location: str = 'Berlin'
    location_terms: str = 'berlin'
    min_score: int = Field(35, ge=0, le=300)
    max_digest_jobs: int = Field(20, ge=1, le=100)
    timezone: str = 'Europe/Berlin'
    schedule_frequency: str = 'weekly'
    schedule_day: str = 'mon'
    schedule_hour: int = Field(8, ge=0, le=23)
    schedule_minute: int = Field(0, ge=0, le=59)
    schedule_interval_hours: int = Field(12, ge=1, le=168)


class NotificationPayload(BaseModel):
    telegram_chat_id: str = ''
    telegram_bot_token: str = ''
    smtp_host: str = ''
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_use_tls: bool = True
    email_from: str = ''
    email_to: str = ''


class SourcePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source_type: str
    enabled: bool = True
    config: dict[str, Any] = {}
    secrets: dict[str, str] = {}


class KeywordPayload(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    kind: str
    weight: int = Field(0, ge=-100, le=100)
    enabled: bool = True


class JobDecisionPayload(BaseModel):
    decision: str


class ApplicationPayload(BaseModel):
    status: str
    notes: str | None = Field(default=None, max_length=4000)
    applied_at: str | None = None


@app.get('/health')
def health():
    job = scheduler.get_job(JOB_ID)
    return {'status': 'ok', 'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None}


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_admin)):
    return templates.TemplateResponse('index.html', {'request': request, 'app_name': settings.app_name})


@app.get('/api/overview')
def overview(_: str = Depends(require_admin)):
    job = scheduler.get_job(JOB_ID)
    runs = list_runs(limit=1)
    return {
        'stats': dashboard_stats(),
        'next_run': job.next_run_time.isoformat() if job and job.next_run_time else None,
        'last_run': runs[0] if runs else None,
        'security': {
            'default_admin_password': settings.admin_password == 'change-me',
            'default_secret_key': settings.app_secret_key == 'change-this-secret-key',
        },
    }


@app.get('/api/settings')
def api_settings(_: str = Depends(require_admin)):
    return get_all_settings(mask_secrets=True)


@app.put('/api/settings')
def update_settings(payload: AppSettingsPayload, _: str = Depends(require_admin)):
    if payload.schedule_frequency not in ('disabled', 'interval', 'daily', 'weekly'):
        raise HTTPException(400, 'Invalid schedule frequency')
    for key, value in payload.model_dump().items():
        set_setting(key, str(value))
    reschedule()
    return {'ok': True}


@app.put('/api/notifications')
def update_notifications(payload: NotificationPayload, _: str = Depends(require_admin)):
    data = payload.model_dump()
    for key in ('telegram_chat_id', 'smtp_host', 'smtp_port', 'smtp_username', 'smtp_use_tls', 'email_from', 'email_to'):
        set_setting(key, str(data[key]).lower() if isinstance(data[key], bool) else str(data[key]))
    # Empty secret input means preserve the current value.
    if payload.telegram_bot_token:
        set_setting('telegram_bot_token', payload.telegram_bot_token, is_secret=True)
    if payload.smtp_password:
        set_setting('smtp_password', payload.smtp_password, is_secret=True)
    return {'ok': True}


@app.post('/api/notifications/test-telegram')
async def api_test_telegram(_: str = Depends(require_admin)):
    await test_telegram(runtime_config())
    return {'ok': True}


@app.post('/api/notifications/test-email')
def api_test_email(_: str = Depends(require_admin)):
    if not test_email(runtime_config()):
        raise HTTPException(400, 'Email settings are incomplete')
    return {'ok': True}


@app.get('/api/sources')
def api_sources(_: str = Depends(require_admin)):
    return {'sources': list_sources(mask_secrets=True)}


@app.post('/api/sources')
def add_source(payload: SourcePayload, _: str = Depends(require_admin)):
    if payload.source_type not in ('rss',):
        raise HTTPException(400, 'Only RSS/Atom sources can be added from the UI')
    source_id = save_source(payload.name, payload.source_type, payload.enabled, payload.config, payload.secrets)
    return {'ok': True, 'id': source_id}


@app.put('/api/sources/{source_id}')
def update_source(source_id: int, payload: SourcePayload, _: str = Depends(require_admin)):
    current = get_source(source_id, mask_secrets=False)
    if not current:
        raise HTTPException(404, 'Source not found')
    if current['source_type'] in ('arbeitnow', 'adzuna') and payload.source_type != current['source_type']:
        raise HTTPException(400, 'Built-in source type cannot be changed')
    save_source(payload.name, payload.source_type, payload.enabled, payload.config, payload.secrets, source_id=source_id)
    return {'ok': True}


@app.delete('/api/sources/{source_id}')
def remove_source(source_id: int, _: str = Depends(require_admin)):
    try:
        delete_source(source_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {'ok': True}


@app.post('/api/sources/{source_id}/test')
async def api_test_source(source_id: int, _: str = Depends(require_admin)):
    source = get_source(source_id, mask_secrets=False)
    if not source:
        raise HTTPException(404, 'Source not found')
    cfg = runtime_config()
    return await test_source(source, list(cfg['keywords']['search'].keys()), cfg['target_location'])


@app.get('/api/keywords')
def api_keywords(_: str = Depends(require_admin)):
    return {'keywords': list_keywords()}


@app.post('/api/keywords')
def add_keyword(payload: KeywordPayload, _: str = Depends(require_admin)):
    if payload.kind not in ('search', 'title', 'format', 'skill', 'negative'):
        raise HTTPException(400, 'Invalid keyword kind')
    try:
        kid = save_keyword(payload.term, payload.kind, payload.weight, payload.enabled)
    except Exception as exc:
        raise HTTPException(400, f'Keyword already exists or is invalid: {exc}') from exc
    return {'ok': True, 'id': kid}


@app.put('/api/keywords/{keyword_id}')
def update_keyword(keyword_id: int, payload: KeywordPayload, _: str = Depends(require_admin)):
    if payload.kind not in ('search', 'title', 'format', 'skill', 'negative'):
        raise HTTPException(400, 'Invalid keyword kind')
    save_keyword(payload.term, payload.kind, payload.weight, payload.enabled, keyword_id=keyword_id)
    return {'ok': True}


@app.delete('/api/keywords/{keyword_id}')
def remove_keyword(keyword_id: int, _: str = Depends(require_admin)):
    delete_keyword(keyword_id)
    return {'ok': True}


@app.post('/run-now')
async def run_now(_: str = Depends(require_admin)):
    return await run_search()


@app.get('/api/jobs')
def api_jobs(
    limit: int = Query(100, ge=1, le=500),
    min_score: int = Query(0, ge=0, le=300),
    decision: str = Query('active'),
    _: str = Depends(require_admin),
):
    if decision not in ('all', 'active', 'unreviewed', 'apply', 'maybe', 'skip'):
        raise HTTPException(400, 'Invalid decision filter')
    return {'jobs': list_jobs(limit=limit, min_score=min_score, decision=None if decision == 'all' else decision)}


@app.put('/api/jobs/{job_key:path}/decision')
def update_job_decision(job_key: str, payload: JobDecisionPayload, _: str = Depends(require_admin)):
    try:
        result = set_job_decision(job_key, payload.decision)
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == 'Invalid decision' else 404, str(exc)) from exc
    return {'ok': True, **result}


@app.get('/api/applications')
def api_applications(
    status: str = Query('all'),
    limit: int = Query(300, ge=1, le=1000),
    _: str = Depends(require_admin),
):
    valid = ('all', 'to_apply', 'applied', 'interview', 'rejected', 'offer')
    if status not in valid:
        raise HTTPException(400, 'Invalid application status filter')
    return {
        'applications': list_applications(None if status == 'all' else status, limit=limit),
        'stats': application_stats(),
    }


@app.put('/api/applications/{job_key:path}')
def update_application(job_key: str, payload: ApplicationPayload, _: str = Depends(require_admin)):
    try:
        result = save_application(job_key, payload.status, notes=payload.notes, applied_at=payload.applied_at)
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == 'Invalid application status' else 404, str(exc)) from exc
    return {'ok': True, **result}


@app.get('/api/runs')
def api_runs(limit: int = Query(30, ge=1, le=200), _: str = Depends(require_admin)):
    return {'runs': list_runs(limit=limit)}
