import json
import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

import httpx

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from . import v10_main as v10
from . import v15_main as v15
from .config import settings
from .database_admin import (
    DatabaseRestoreBusy,
    DatabaseRestoreFailed,
    InvalidDatabaseBackup,
    create_download_backup,
    create_restore_staging_file,
    remove_temporary_database,
    restore_database,
)
from .db import connection, list_sources, save_source
from .job_enrichment import fetch_public_job
from .matching_diagnostics import (
    diagnose_job,
    ensure_matching_diagnostic_schema,
    list_benchmarks,
    run_benchmarks,
    save_benchmark,
)
from .profile_store import get_profile
from .source_analytics import query_quality_summary, search_job_source_summary
from .security import (
    SESSION_COOKIE,
    authenticate_admin,
    create_admin_session,
    current_admin,
    current_user,
    record_login_failure,
    record_login_success,
    require_admin,
    require_login_attempt_allowed,
    require_same_origin,
    require_user,
    require_workspace,
)
from . import system_mail
from .system_mail import SystemMailError
from .user_store import (
    AccountError,
    authenticate_user,
    complete_registration,
    create_registration,
    create_user_session,
    ensure_user_schema,
    list_accounts,
    revoke_all_user_sessions,
    registration_for_token,
    RegistrationError,
    revoke_registration,
    revoke_user_session,
    set_user_status,
)
from .update_client import (
    UpdateAgentError,
    check_for_updates,
    require_same_origin_update,
    start_update,
    update_status,
)
from .version import VERSION

app = v15.app
app.version = VERSION

_inherited_lifespan = app.router.lifespan_context


@asynccontextmanager
async def v17_account_lifespan(application):
    async with _inherited_lifespan(application):
        ensure_user_schema()
        ensure_matching_diagnostic_schema()
        yield


app.router.lifespan_context = v17_account_lifespan

# Replace the inherited dashboard and public health routes so the active shell and
# monitoring endpoint always report the current release instead of an older base layer.
app.router.routes[:] = [
    r
    for r in app.router.routes
    if not (getattr(r, "path", None) in {"/", "/health"} and "GET" in (getattr(r, "methods", set()) or set()))
]


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    if current_admin(request):
        return RedirectResponse("/app", status_code=303)
    if current_user(request):
        return RedirectResponse("/account", status_code=303)
    html = Path("app/templates/login.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{ app_name }}", settings.app_name).replace("{{ version }}", VERSION))


class AdminLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)


class UserLoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class ActivateAccountPayload(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=1024)


class RegisterEmailPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class UserStatusPayload(BaseModel):
    status: str


class SystemEmailSettingsPayload(BaseModel):
    public_base_url: str = Field(default="", max_length=2048)
    registration_lifetime_hours: int = Field(default=24, ge=1, le=168)
    system_smtp_host: str = Field(default="", max_length=253)
    system_smtp_port: int = Field(default=587, ge=1, le=65535)
    system_smtp_username: str = Field(default="", max_length=320)
    system_smtp_password: str = Field(default="", max_length=1024)
    system_smtp_use_tls: bool = True
    system_email_from: str = Field(default="", max_length=320)


class SystemEmailTestPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class MatchingDiagnosticPayload(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=50_000)
    published_at: str = Field(default="", max_length=80)
    remote: bool = False
    fetch_details: bool = True
    save_benchmark: bool = False
    expected_relevant: bool = True
    note: str = Field(default="", max_length=2000)


@app.post("/auth/admin-login")
def admin_login(payload: AdminLoginPayload, request: Request):
    if not authenticate_admin(request, payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    response = Response(content=json.dumps({"ok": True, "redirect": "/app"}), media_type="application/json")
    response.set_cookie(
        SESSION_COOKIE,
        create_admin_session(),
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@app.post("/auth/user-login")
def user_login(payload: UserLoginPayload, request: Request):
    require_login_attempt_allowed(request)
    user = authenticate_user(payload.email, payload.password)
    if not user:
        record_login_failure(request)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    record_login_success(request)
    token = create_user_session(
        user["id"],
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    response = Response(content=json.dumps({"ok": True, "redirect": "/account"}), media_type="application/json")
    _set_session_cookie(response, token)
    return response


@app.post("/auth/register", status_code=202)
def request_registration(payload: RegisterEmailPayload, request: Request):
    require_login_attempt_allowed(request)
    try:
        created = create_registration(
            payload.email,
            request.client.host if request.client else "unknown",
        )
    except AccountError as exc:
        record_login_failure(request)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if created:
        registration_id, token = created
        try:
            system_mail.send_activation_email(payload.email.strip().lower(), token)
        except SystemMailError as exc:
            revoke_registration(registration_id, "system", action="user.registration_delivery_failed")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    record_login_success(request)
    return {
        "ok": True,
        "message": "If this email can be registered, an activation link has been sent.",
    }


@app.get("/activate", response_class=HTMLResponse)
def activation_page(token: str = ""):
    registration = registration_for_token(token)
    html = Path("app/templates/activate.html").read_text(encoding="utf-8")
    replacements = {
        "{{ app_name }}": settings.app_name,
        "{{ version }}": VERSION,
        "{{ token_json }}": json.dumps(token).replace("<", "\\u003c"),
        "{{ email }}": escape(registration["email"]) if registration else "",
        "{{ form_hidden }}": "" if registration else "hidden",
        "{{ invalid_hidden }}": "hidden" if registration else "",
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.post("/auth/activate")
def activate_account(payload: ActivateAccountPayload, request: Request):
    require_login_attempt_allowed(request)
    try:
        user = complete_registration(payload.token, payload.full_name, payload.password)
    except (AccountError, RegistrationError) as exc:
        record_login_failure(request)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_login_success(request)
    token = create_user_session(
        user["id"],
        request.client.host if request.client else "",
        request.headers.get("user-agent", ""),
    )
    response = Response(content=json.dumps({"ok": True, "redirect": "/account"}), media_type="application/json")
    _set_session_cookie(response, token)
    return response


@app.post("/auth/logout")
def logout(request: Request):
    if not current_admin(request):
        revoke_user_session(request.cookies.get(SESSION_COOKIE))
    response = Response(content=json.dumps({"ok": True, "redirect": "/"}), media_type="application/json")
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@app.get("/account", response_class=HTMLResponse)
def account_page(user: dict = Depends(require_user)):
    html = Path("app/templates/account.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("{{ app_name }}", settings.app_name)
        .replace("{{ version }}", VERSION)
        .replace("{{ full_name }}", escape(user["full_name"]))
        .replace("{{ email }}", escape(user["email"]))
        .replace("Your account is active.", "Your private workspace is ready.")
        .replace(
            "Your private workspace will open after the per-user data migration is completed. "
            "Until then, administrator data remains isolated and unavailable.",
            "Profiles, searches, applications and notification settings are isolated to your account. "
            '<a href="/app">Open my workspace</a>',
        ),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/app", response_class=HTMLResponse)
def dashboard(request: Request, actor: dict = Depends(require_workspace)):
    is_admin = actor["kind"] == "admin"
    html = Path("app/templates/index.html").read_text(encoding="utf-8").replace("{{ app_name }}", settings.app_name)
    html = html.replace("<body>", '<body data-job-review-ui="true">', 1)
    html = html.replace(
        "Supply Chain Tracker<small>Berlin / Brandenburg · v3</small>",
        f"{settings.app_name}<small>Smart Job Search · v{VERSION}</small>",
    )
    shell_config_data = {"appName": settings.app_name, "version": VERSION}
    shell_config_data["isAdmin"] = is_admin
    shell_config = json.dumps(
        shell_config_data,
        ensure_ascii=True,
    ).replace("<", "\\u003c")
    business_scripts = (
        '<script src="/language-ui.js"></script>'
        '<script src="/review-ui.js"></script>'
        '<script src="/source-options-ui.js"></script>'
        '<script src="/legacy-compat-ui.js"></script>'
        '<script src="/profile-ui.js"></script>'
        '<script src="/applications-profile-ui.js"></script>'
        '<script src="/search-job-ui.js"></script>'
        '<script src="/matching-diagnostics-ui.js"></script>'
        '<script src="/intelligence-ui.js"></script>'
        '<script src="/intelligence-settings-ui.js"></script>'
        '<script src="/semantic-settings-ui.js"></script>'
    )
    admin_scripts = (
        '<script src="/source-ui.js"></script>'
        '<script src="/stepstone-ui.js"></script>'
        '<script src="/jobspy-ui.js"></script>'
        '<script src="/source-analytics-ui.js"></script>'
        '<script src="/database-ui.js"></script>'
        '<script src="/log-ui.js"></script>'
        '<script src="/update-ui.js"></script>'
        '<script src="/users-ui.js"></script>'
        '<script src="/system-email-ui.js"></script>'
    )
    scripts = (
        business_scripts + (admin_scripts if is_admin else "") + f"<script>window.APP_SHELL={shell_config};</script>"
        f'<script src="/ui-shell.js?v={VERSION}"></script>'
    )
    if not is_admin:
        html = html.replace(
            "refreshAll();",
            "Promise.all([loadOverview(),loadJobs(),loadApplications(),loadSettings()]).catch(e=>toast(e.message,true));",
        )
    return HTMLResponse(html.replace("</body>", scripts + "</body>"))


@app.get("/matching-diagnostics-ui.js")
def matching_diagnostics_ui(_: dict = Depends(require_workspace)):
    return Response(
        Path("app/matching-diagnostics-ui.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


@app.get("/source-options-ui.js")
def source_options_ui(_: dict = Depends(require_workspace)):
    return Response(Path("app/source-options-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/semantic-settings-ui.js")
def semantic_settings_ui(_: dict = Depends(require_workspace)):
    return Response(
        Path("app/semantic-settings-ui.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


def _diagnostic_context(search_job_id: int, actor: dict) -> tuple[dict, dict]:
    search_job = v10.get_search_job(search_job_id, True, user_id=actor["user_id"])
    if not search_job:
        raise HTTPException(status_code=404, detail="Search job not found")
    profile = get_profile(int(search_job["profile_id"]), user_id=actor["user_id"])
    if not profile:
        raise HTTPException(status_code=404, detail="Search profile not found")
    return search_job, profile


@app.post("/api/search-jobs/{search_job_id}/diagnose")
async def api_diagnose_matching(
    search_job_id: int,
    payload: MatchingDiagnosticPayload,
    actor: dict = Depends(require_workspace),
):
    search_job, profile = _diagnostic_context(search_job_id, actor)
    values = payload.model_dump()
    if payload.fetch_details and (not payload.title or len(payload.description.split()) < 35):
        try:
            fetched = await fetch_public_job(payload.url)
        except (ValueError, httpx.HTTPError) as exc:
            if not payload.title:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            values["detail_fetch_error"] = str(exc)
        else:
            for key in ("title", "company", "location", "description", "published_at"):
                if fetched.get(key) and (not values.get(key) or key == "description"):
                    values[key] = fetched[key]
            if fetched.get("employment_type"):
                values["description"] = (
                    f"Employment type: {fetched['employment_type']}\n{values.get('description', '')}"
                ).strip()
    if not str(values.get("title") or "").strip():
        raise HTTPException(status_code=400, detail="A job title could not be extracted")
    diagnosis = diagnose_job(values, search_job, profile)
    if values.get("detail_fetch_error"):
        diagnosis["detail_fetch_error"] = values["detail_fetch_error"]
    if payload.save_benchmark:
        diagnosis["benchmark_id"] = save_benchmark(values, search_job, profile, diagnosis, user_id=actor["user_id"])
    return diagnosis


@app.get("/api/search-jobs/{search_job_id}/benchmarks")
def api_matching_benchmarks(search_job_id: int, actor: dict = Depends(require_workspace)):
    _diagnostic_context(search_job_id, actor)
    return {"benchmarks": list_benchmarks(search_job_id, user_id=actor["user_id"])}


@app.delete("/api/search-jobs/{search_job_id}/benchmarks/{benchmark_id}")
def api_delete_matching_benchmark(
    search_job_id: int,
    benchmark_id: int,
    actor: dict = Depends(require_workspace),
):
    _diagnostic_context(search_job_id, actor)
    with connection() as con:
        cursor = con.execute(
            "DELETE FROM matching_benchmarks WHERE id=? AND search_job_id=? AND user_id=?",
            (benchmark_id, search_job_id, actor["user_id"] if actor["user_id"] is not None else 0),
        )
    if not cursor.rowcount:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return {"ok": True}


@app.post("/api/search-jobs/{search_job_id}/benchmarks/run")
def api_run_matching_benchmarks(search_job_id: int, actor: dict = Depends(require_workspace)):
    search_job, profile = _diagnostic_context(search_job_id, actor)
    return run_benchmarks(search_job, profile, user_id=actor["user_id"])


@app.get("/api/search-jobs/{search_job_id}/quality")
def api_search_job_quality(search_job_id: int, actor: dict = Depends(require_workspace)):
    _diagnostic_context(search_job_id, actor)
    return {
        "sources": search_job_source_summary(search_job_id, user_id=actor["user_id"]),
        "queries": query_quality_summary(search_job_id, user_id=actor["user_id"]),
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/stepstone-ui.js")
def stepstone_ui(_: str = Depends(require_admin)):
    return Response(Path("app/stepstone-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


class StepStonePayload(BaseModel):
    name: str = Field(default="StepStone Germany", min_length=1, max_length=100)
    enabled: bool = False
    max_search_terms: int = Field(default=6, ge=1, le=10)
    pages_per_term: int = Field(default=1, ge=1, le=3)
    results_per_term: int = Field(default=25, ge=1, le=75)
    timeout_seconds: int = Field(default=30, ge=10, le=90)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=5)


@app.get("/api/stepstone/source")
def get_stepstone_source(_: str = Depends(require_admin)):
    source = next((s for s in list_sources(mask_secrets=True) if s["source_type"] == "stepstone"), None)
    return {"source": source}


@app.put("/api/stepstone/source")
def configure_stepstone(payload: StepStonePayload, _: str = Depends(require_admin)):
    current = next((s for s in list_sources(mask_secrets=False) if s["source_type"] == "stepstone"), None)
    config = {
        "max_search_terms": payload.max_search_terms,
        "pages_per_term": payload.pages_per_term,
        "results_per_term": payload.results_per_term,
        "timeout_seconds": payload.timeout_seconds,
        "request_delay_seconds": payload.request_delay_seconds,
    }
    source_id = save_source(
        payload.name,
        "stepstone",
        payload.enabled,
        config,
        {},
        source_id=current["id"] if current else None,
    )
    return {"ok": True, "id": source_id, "enabled": payload.enabled, "config": config}


@app.get("/legacy-compat-ui.js")
def legacy_compat_ui(_: dict = Depends(require_workspace)):
    return Response(Path("app/legacy-compat-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/ui-shell.js")
def ui_shell(_: dict = Depends(require_workspace)):
    return Response(
        Path("app/ui-shell.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/users-ui.js")
def users_ui(_: str = Depends(require_admin)):
    return Response(Path("app/users-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/system-email-ui.js")
def system_email_ui(_: str = Depends(require_admin)):
    return Response(Path("app/system-email-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/api/admin/system-email")
def api_system_email_settings(_: str = Depends(require_admin)):
    try:
        return system_mail.get_system_mail_config(mask_secret=True)
    except SystemMailError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/admin/system-email")
def api_update_system_email_settings(
    payload: SystemEmailSettingsPayload,
    request: Request,
    admin: str = Depends(require_admin),
):
    require_same_origin(request)
    data = payload.model_dump()
    base_url = data["public_base_url"].strip().rstrip("/")
    if base_url:
        from urllib.parse import urlsplit

        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(400, "Public base URL must be an absolute HTTP or HTTPS URL")
    data["public_base_url"] = base_url
    data["system_smtp_host"] = data["system_smtp_host"].strip()
    data["system_smtp_username"] = data["system_smtp_username"].strip()
    data["system_email_from"] = data["system_email_from"].strip()
    system_mail.save_system_mail_config(data)
    from .user_store import record_audit

    record_audit(admin, "system_email.settings_updated")
    return {"ok": True, "configured": system_mail.get_system_mail_config(mask_secret=True)["configured"]}


@app.post("/api/admin/system-email/test")
def api_test_system_email(
    payload: SystemEmailTestPayload,
    request: Request,
    admin: str = Depends(require_admin),
):
    require_same_origin(request)
    try:
        system_mail.send_test_email(payload.email)
    except SystemMailError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from .user_store import record_audit

    record_audit(admin, "system_email.test_sent", payload.email.strip().lower())
    return {"ok": True}


@app.get("/api/admin/users")
def api_admin_users(_: str = Depends(require_admin)):
    return list_accounts()


@app.post("/api/admin/registrations/{registration_id}/revoke")
def api_revoke_registration(registration_id: int, request: Request, admin: str = Depends(require_admin)):
    require_same_origin(request)
    if not revoke_registration(registration_id, admin):
        raise HTTPException(status_code=404, detail="Pending registration not found")
    return {"ok": True}


@app.put("/api/admin/users/{user_id}/status")
def api_set_user_status(
    user_id: int, payload: UserStatusPayload, request: Request, admin: str = Depends(require_admin)
):
    require_same_origin(request)
    try:
        changed = set_user_status(user_id, payload.status, admin)
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "status": payload.status}


@app.post("/api/admin/users/{user_id}/revoke-sessions")
def api_revoke_user_sessions(user_id: int, request: Request, admin: str = Depends(require_admin)):
    require_same_origin(request)
    if not revoke_all_user_sessions(user_id, admin):
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@app.get("/update-ui.js")
def update_ui(_: str = Depends(require_admin)):
    return Response(Path("app/update-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


class ApplyUpdatePayload(BaseModel):
    confirmation: str = Field(max_length=40)


def _update_response(action):
    try:
        return action()
    except UpdateAgentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/update/status")
def api_update_status(_: str = Depends(require_admin)):
    return _update_response(update_status)


@app.post("/api/update/check")
def api_check_for_updates(request: Request, _: str = Depends(require_admin)):
    require_same_origin_update(request)
    return _update_response(check_for_updates)


@app.post("/api/update/apply", status_code=202)
def api_apply_update(payload: ApplyUpdatePayload, request: Request, _: str = Depends(require_admin)):
    require_same_origin_update(request)
    if payload.confirmation != "APPLY UPDATE":
        raise HTTPException(status_code=400, detail="Update confirmation is invalid")
    return _update_response(start_update)


def _require_database_action(request: Request, expected: str) -> None:
    require_same_origin(request)
    if request.headers.get("x-bert-action") != expected:
        raise HTTPException(status_code=400, detail="Missing or invalid database action header")


@app.post("/api/database/backup")
def api_download_database_backup(request: Request, _: str = Depends(require_admin)):
    _require_database_action(request, "backup")
    path, filename = create_download_backup()
    return FileResponse(
        path,
        media_type="application/vnd.sqlite3",
        filename=filename,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(remove_temporary_database, path),
    )


@app.post("/api/database/restore")
async def api_restore_database(request: Request, _: str = Depends(require_admin)):
    _require_database_action(request, "restore")
    if request.headers.get("x-bert-confirmation") != "RESTORE DATABASE":
        raise HTTPException(status_code=400, detail="Restore confirmation is invalid")

    max_bytes = settings.database_restore_max_bytes
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Uploaded backup is too large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header") from exc

    staging_path = create_restore_staging_file()
    uploaded_bytes = 0
    try:
        with open(staging_path, "wb") as handle:
            async for chunk in request.stream():
                uploaded_bytes += len(chunk)
                if uploaded_bytes > max_bytes:
                    raise HTTPException(status_code=413, detail="Uploaded backup is too large")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if uploaded_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded backup is empty")
        try:
            result = await run_in_threadpool(restore_database, staging_path)
        except InvalidDatabaseBackup as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DatabaseRestoreBusy as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DatabaseRestoreFailed as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        v10.reschedule_search_jobs()
        return {**result, "uploaded_bytes": uploaded_bytes, "scheduler_rescheduled": True}
    finally:
        remove_temporary_database(staging_path)


_FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#2563eb"/><path d="M17 18h30v8H36v24h-9V26H17z" fill="white"/>
</svg>"""


@app.get("/favicon.svg", include_in_schema=False)
def favicon_svg():
    return Response(_FAVICON, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico():
    return Response(_FAVICON, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def apple_touch_icon():
    return Response(status_code=204, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/v16-health")
def v16_health(_: str = Depends(require_admin)):
    return {
        "status": "ok",
        "version": app.version,
        "responsive_ui": True,
        "mobile_navigation": True,
        "mobile_tables": True,
        "reset_refresh_fix": True,
        "employment_format_filter": True,
        "legacy_jobs_refresh_fix": True,
        "stepstone_experimental_provider": True,
        "hybrid_cv_intelligence": True,
        "evidence_based_cv_match": True,
        "ollama_context_weight": 30,
        "intelligence_cache": True,
        "web_update_management": True,
        "web_database_backup_restore": True,
        "email_self_registration": True,
        "registered_user_sessions": True,
    }
