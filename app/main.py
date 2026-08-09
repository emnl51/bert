from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from starlette.requests import Request

from .config import settings, validate_secure_settings
from .db import (
    application_stats,
    dashboard_stats,
    delete_keyword,
    delete_source,
    get_all_settings,
    get_source,
    init_db,
    list_applications,
    list_keywords,
    list_runs,
    list_sources,
    save_application,
    save_keyword,
    save_source,
    set_job_decision,
    set_job_content_language,
    set_setting,
)
from .feedback_store import (
    delete_rule,
    ensure_feedback_schema,
    feedback_stats,
    list_feedback,
    list_learned_rules,
    record_feedback,
    set_rule_enabled,
)
from .language_store import ensure_language_schema, enrich_applications
from .notifier import test_email, test_telegram
from .profile_store import (
    delete_profile,
    ensure_profile_schema,
    get_profile,
    list_jobs_for_profile,
    list_profiles,
    save_profile,
)
from .providers import test_source
from .runtime import runtime_config
from .source_catalog import SOURCE_CATALOG
from .security import CSRFMiddleware, require_admin
from .service import run_search

scheduler = AsyncIOScheduler(timezone=settings.timezone)
JOB_ID = "scheduled_job_search"


def build_trigger(cfg: dict):
    frequency = cfg["schedule_frequency"]
    if frequency == "disabled":
        return None
    if frequency == "interval":
        return IntervalTrigger(hours=max(1, cfg["schedule_interval_hours"]), timezone=cfg["timezone"])
    if frequency == "daily":
        return CronTrigger(hour=cfg["schedule_hour"], minute=cfg["schedule_minute"], timezone=cfg["timezone"])
    return CronTrigger(
        day_of_week=cfg["schedule_day"],
        hour=cfg["schedule_hour"],
        minute=cfg["schedule_minute"],
        timezone=cfg["timezone"],
    )


def reschedule() -> None:
    cfg = runtime_config()
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    trigger = build_trigger(cfg)
    if trigger:
        scheduler.add_job(run_search, trigger, id=JOB_ID, replace_existing=True, max_instances=1, coalesce=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secure_settings()
    init_db()
    ensure_language_schema()
    ensure_profile_schema()
    ensure_feedback_schema()
    reschedule()
    scheduler.start()
    if settings.run_on_start:
        asyncio.create_task(run_search())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, version="9.0.0", lifespan=lifespan)
app.add_middleware(CSRFMiddleware)


class AppSettingsPayload(BaseModel):
    target_location: str = "Berlin"
    location_terms: str = "berlin"
    min_score: int = Field(35, ge=0, le=100)
    max_digest_jobs: int = Field(20, ge=1, le=100)
    timezone: str = "Europe/Berlin"
    schedule_frequency: str = "weekly"
    schedule_day: str = "mon"
    schedule_hour: int = Field(8, ge=0, le=23)
    schedule_minute: int = Field(0, ge=0, le=59)
    schedule_interval_hours: int = Field(12, ge=1, le=168)
    primary_working_language: str = "English"
    current_german_level: str = "a2_b1"
    max_german_requirement: str = "b1"
    min_language_score: int = Field(40, ge=0, le=100)
    language_weight: int = Field(35, ge=0, le=100)
    show_b2_stretch: bool = True
    hide_german_heavy: bool = True
    prefer_german_growth: bool = True


class NotificationPayload(BaseModel):
    telegram_chat_id: str = ""
    telegram_bot_token: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = ""
    email_to: str = ""


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


class ProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    is_default: bool = False
    target_location: str = "Berlin"
    location_terms: list[str] = []
    min_score: int = Field(35, ge=0, le=100)
    min_language_score: int = Field(40, ge=0, le=100)
    language_weight: int = Field(35, ge=0, le=100)
    current_german_level: str = "a2_b1"
    max_german_requirement: str = "b1"
    show_b2_stretch: bool = True
    hide_german_heavy: bool = True
    prefer_german_growth: bool = True
    content_languages: list[str] = ["de", "en", "mixed"]
    keywords: dict[str, dict[str, int]] = {}


class JobDecisionPayload(BaseModel):
    decision: str


class JobContentLanguagePayload(BaseModel):
    language: str


class ApplicationPayload(BaseModel):
    status: str
    notes: str | None = Field(default=None, max_length=4000)
    applied_at: str | None = None


class FeedbackPayload(BaseModel):
    suitability: str
    reason: str = ""
    note: str = Field(default="", max_length=2000)
    learn: bool = True
    profile_id: int = 1


class RuleTogglePayload(BaseModel):
    enabled: bool


@app.get("/health")
def health():
    job = scheduler.get_job(JOB_ID)
    return {
        "status": "ok",
        "version": "9.0.0",
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_admin)):
    html = Path("app/templates/index.html").read_text(encoding="utf-8").replace("{{ app_name }}", settings.app_name)
    html = html.replace(
        "</body>",
        '<script src="/language-ui.js"></script><script src="/source-ui.js"></script><script src="/review-ui.js"></script><script src="/profile-ui.js"></script></body>',
    )
    return HTMLResponse(html)


@app.get("/language-ui.js")
def language_ui(_: str = Depends(require_admin)):
    return Response(Path("app/language-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/source-ui.js")
def source_ui(_: str = Depends(require_admin)):
    return Response(Path("app/source-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/review-ui.js")
def review_ui(_: str = Depends(require_admin)):
    return Response(Path("app/review-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/profile-ui.js")
def profile_ui(_: str = Depends(require_admin)):
    return Response(Path("app/profile-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/api/overview")
def overview(_: str = Depends(require_admin)):
    job = scheduler.get_job(JOB_ID)
    runs = list_runs(limit=1)
    default = get_profile()
    return {
        "stats": {**dashboard_stats(), **feedback_stats(default["id"] if default else None)},
        "default_profile": default,
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "last_run": runs[0] if runs else None,
        "security": {
            "default_admin_password": settings.admin_password == "change-me",
            "default_secret_key": settings.app_secret_key == "change-this-secret-key",
        },
    }


@app.get("/api/settings")
def api_settings(_: str = Depends(require_admin)):
    return get_all_settings(mask_secrets=True)


@app.put("/api/settings")
def update_settings(payload: AppSettingsPayload, _: str = Depends(require_admin)):
    if payload.schedule_frequency not in ("disabled", "interval", "daily", "weekly"):
        raise HTTPException(400, "Invalid schedule frequency")
    for key, value in payload.model_dump().items():
        set_setting(key, str(value).lower() if isinstance(value, bool) else str(value))
    reschedule()
    return {"ok": True}


@app.put("/api/notifications")
def update_notifications(payload: NotificationPayload, _: str = Depends(require_admin)):
    data = payload.model_dump()
    for key in (
        "telegram_chat_id",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_use_tls",
        "email_from",
        "email_to",
    ):
        set_setting(key, str(data[key]).lower() if isinstance(data[key], bool) else str(data[key]))
    if payload.telegram_bot_token:
        set_setting("telegram_bot_token", payload.telegram_bot_token, is_secret=True)
    if payload.smtp_password:
        set_setting("smtp_password", payload.smtp_password, is_secret=True)
    return {"ok": True}


@app.post("/api/notifications/test-telegram")
async def api_test_telegram(_: str = Depends(require_admin)):
    await test_telegram(runtime_config())
    return {"ok": True}


@app.post("/api/notifications/test-email")
def api_test_email(_: str = Depends(require_admin)):
    if not test_email(runtime_config()):
        raise HTTPException(400, "Email settings are incomplete")
    return {"ok": True}


@app.get("/api/profiles")
def api_profiles(_: str = Depends(require_admin)):
    return {"profiles": list_profiles()}


@app.post("/api/profiles")
def create_profile(payload: ProfilePayload, _: str = Depends(require_admin)):
    try:
        return {"ok": True, "id": save_profile(payload.model_dump())}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, payload: ProfilePayload, _: str = Depends(require_admin)):
    if not get_profile(profile_id):
        raise HTTPException(404, "Profile not found")
    try:
        save_profile(payload.model_dump(), profile_id)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/profiles/{profile_id}")
def remove_profile(profile_id: int, _: str = Depends(require_admin)):
    try:
        delete_profile(profile_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/source-catalog")
def api_source_catalog(_: str = Depends(require_admin)):
    return {"catalog": SOURCE_CATALOG}


@app.get("/api/sources")
def api_sources(_: str = Depends(require_admin)):
    return {"sources": list_sources(mask_secrets=True)}


@app.post("/api/sources")
def add_source(payload: SourcePayload, _: str = Depends(require_admin)):
    if payload.source_type not in {"rss", "search_link", "jooble", "greenhouse", "lever", "smartrecruiters"}:
        raise HTTPException(400, "Unsupported source type")
    return {
        "ok": True,
        "id": save_source(payload.name, payload.source_type, payload.enabled, payload.config, payload.secrets),
    }


@app.put("/api/sources/{source_id}")
def update_source(source_id: int, payload: SourcePayload, _: str = Depends(require_admin)):
    current = get_source(source_id, mask_secrets=False)
    if not current:
        raise HTTPException(404, "Source not found")
    save_source(
        payload.name, payload.source_type, payload.enabled, payload.config, payload.secrets, source_id=source_id
    )
    return {"ok": True}


@app.delete("/api/sources/{source_id}")
def remove_source(source_id: int, _: str = Depends(require_admin)):
    try:
        delete_source(source_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/sources/{source_id}/test")
async def api_test_source(source_id: int, _: str = Depends(require_admin)):
    source = get_source(source_id, mask_secrets=False)
    if not source:
        raise HTTPException(404, "Source not found")
    cfg = runtime_config()
    return await test_source(source, list(cfg["keywords"]["search"].keys()), cfg["target_location"])


@app.get("/api/keywords")
def api_keywords(_: str = Depends(require_admin)):
    return {"keywords": list_keywords()}


@app.post("/api/keywords")
def add_keyword(payload: KeywordPayload, _: str = Depends(require_admin)):
    if payload.kind not in ("search", "title", "format", "skill", "negative"):
        raise HTTPException(400, "Invalid keyword kind")
    try:
        return {"ok": True, "id": save_keyword(payload.term, payload.kind, payload.weight, payload.enabled)}
    except Exception as exc:
        raise HTTPException(400, f"Keyword already exists or is invalid: {exc}") from exc


@app.put("/api/keywords/{keyword_id}")
def update_keyword(keyword_id: int, payload: KeywordPayload, _: str = Depends(require_admin)):
    save_keyword(payload.term, payload.kind, payload.weight, payload.enabled, keyword_id=keyword_id)
    return {"ok": True}


@app.delete("/api/keywords/{keyword_id}")
def remove_keyword(keyword_id: int, _: str = Depends(require_admin)):
    delete_keyword(keyword_id)
    return {"ok": True}


@app.post("/run-now")
async def run_now(_: str = Depends(require_admin)):
    return await run_search()


@app.get("/api/jobs")
def api_jobs(
    limit: int = Query(100, ge=1, le=500),
    min_score: int = Query(0, ge=0, le=100),
    decision: str = Query("active"),
    language: str = Query("preferred"),
    content_language: str = Query("profile"),
    profile_id: int | None = Query(None),
    _: str = Depends(require_admin),
):
    if decision not in ("all", "active", "unreviewed", "apply", "maybe", "skip"):
        raise HTTPException(400, "Invalid decision filter")
    if language not in ("all", "preferred", "english_first", "german_growth", "stretch", "german_heavy", "unclear"):
        raise HTTPException(400, "Invalid language filter")
    if content_language not in ("all", "profile", "de", "en", "mixed", "unknown"):
        raise HTTPException(400, "Invalid content language filter")
    profile = get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return {
        "profile": profile,
        "jobs": list_jobs_for_profile(
            profile["id"], limit, min_score, None if decision == "all" else decision, language, content_language
        ),
    }


@app.put("/api/jobs/{job_key:path}/decision")
def update_job_decision(job_key: str, payload: JobDecisionPayload, _: str = Depends(require_admin)):
    try:
        return {"ok": True, **set_job_decision(job_key, payload.decision)}
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == "Invalid decision" else 404, str(exc)) from exc


@app.put("/api/jobs/{job_key:path}/content-language")
def update_job_content_language(job_key: str, payload: JobContentLanguagePayload, _: str = Depends(require_admin)):
    try:
        return {"ok": True, **set_job_content_language(job_key, payload.language)}
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == "Invalid content language" else 404, str(exc)) from exc


@app.post("/api/jobs/{job_key:path}/feedback")
def add_job_feedback(job_key: str, payload: FeedbackPayload, _: str = Depends(require_admin)):
    try:
        return {
            "ok": True,
            **record_feedback(
                job_key, payload.suitability, payload.reason, payload.note, payload.learn, payload.profile_id
            ),
        }
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == "Invalid suitability" else 404, str(exc)) from exc


@app.get("/api/learning")
def learning(profile_id: int | None = Query(None), _: str = Depends(require_admin)):
    profile = get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    return {
        "profile": profile,
        "stats": feedback_stats(profile["id"]),
        "rules": list_learned_rules(profile["id"]),
        "feedback": list_feedback(100, profile["id"]),
    }


@app.put("/api/learning/rules/{rule_id}")
def toggle_learning_rule(rule_id: int, payload: RuleTogglePayload, _: str = Depends(require_admin)):
    set_rule_enabled(rule_id, payload.enabled)
    return {"ok": True}


@app.delete("/api/learning/rules/{rule_id}")
def remove_learning_rule(rule_id: int, _: str = Depends(require_admin)):
    delete_rule(rule_id)
    return {"ok": True}


@app.get("/api/applications")
def api_applications(
    status: str = Query("all"), limit: int = Query(300, ge=1, le=1000), _: str = Depends(require_admin)
):
    valid = ("all", "to_apply", "applied", "interview", "rejected", "offer")
    if status not in valid:
        raise HTTPException(400, "Invalid application status filter")
    return {
        "applications": enrich_applications(list_applications(None if status == "all" else status, limit=limit)),
        "stats": application_stats(),
    }


@app.put("/api/applications/{job_key:path}")
def update_application(job_key: str, payload: ApplicationPayload, _: str = Depends(require_admin)):
    try:
        return {
            "ok": True,
            **save_application(job_key, payload.status, notes=payload.notes, applied_at=payload.applied_at),
        }
    except ValueError as exc:
        raise HTTPException(400 if str(exc) == "Invalid application status" else 404, str(exc)) from exc


@app.get("/api/runs")
def api_runs(limit: int = Query(30, ge=1, le=200), _: str = Depends(require_admin)):
    return {"runs": list_runs(limit=limit)}
