from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from starlette.requests import Request

from . import v10_main as v10
from .candidate_store import (
    assign_candidate,
    candidate_for_search_job,
    delete_candidate,
    ensure_candidate_schema,
    get_candidate,
    list_candidates,
    mapping_for_jobs,
    save_candidate,
)
from .intelligence import analyze_job, ensure_intelligence_schema, get_analysis, list_analyses
from .search_job_store import get_search_job
from .security import require_admin, require_workspace
from .config import settings
from .db import get_setting, set_setting

app = v10.app
_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def v11_lifespan(application):
    async with _original_lifespan(application):
        ensure_candidate_schema()
        ensure_intelligence_schema()
        yield


app.router.lifespan_context = v11_lifespan
app.version = "11.0.0"

app.router.routes[:] = [
    r
    for r in app.router.routes
    if not (getattr(r, "path", None) == "/" and "GET" in (getattr(r, "methods", set()) or set()))
]


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_admin)):
    html = Path("app/templates/index.html").read_text(encoding="utf-8").replace("{{ app_name }}", settings.app_name)
    scripts = '<script src="/language-ui.js"></script><script src="/source-ui.js"></script><script src="/review-ui.js"></script><script src="/profile-ui.js"></script><script src="/search-job-ui.js"></script><script src="/intelligence-ui.js"></script><script src="/intelligence-settings-ui.js"></script>'
    return HTMLResponse(html.replace("</body>", scripts + "</body>"))


class CandidatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    headline: str = ""
    cv_text: str = Field(default="", max_length=50000)
    skills: list[str] = []
    languages: dict[str, str] = {}
    target_roles: list[str] = []
    notes: str = Field(default="", max_length=10000)


class CandidateAssignmentPayload(BaseModel):
    candidate_profile_id: int | None = None
    enabled: bool = True


class IntelligenceSettingsPayload(BaseModel):
    ollama_enabled: bool = False
    ollama_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "gemma3"
    ollama_timeout_seconds: int = Field(default=60, ge=10, le=120)


@app.get("/intelligence-ui.js")
def intelligence_ui(_: dict = Depends(require_workspace)):
    return Response(Path("app/intelligence-ui.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/intelligence-settings-ui.js")
def intelligence_settings_ui(_: dict = Depends(require_workspace)):
    return Response(
        Path("app/intelligence-settings-ui.js").read_text(encoding="utf-8"), media_type="application/javascript"
    )


@app.get("/api/candidates")
def api_candidates(actor: dict = Depends(require_workspace)):
    return {
        "candidates": list_candidates(user_id=actor["user_id"]),
        "assignments": mapping_for_jobs(user_id=actor["user_id"]),
    }


@app.post("/api/candidates")
def create_candidate(payload: CandidatePayload, actor: dict = Depends(require_workspace)):
    try:
        return {"ok": True, "id": save_candidate(payload.model_dump(), user_id=actor["user_id"])}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/candidates/{candidate_id}")
def update_candidate(candidate_id: int, payload: CandidatePayload, actor: dict = Depends(require_workspace)):
    if not get_candidate(candidate_id, user_id=actor["user_id"]):
        raise HTTPException(404, "Candidate profile not found")
    try:
        save_candidate(payload.model_dump(), candidate_id, user_id=actor["user_id"])
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/candidates/{candidate_id}")
def remove_candidate(candidate_id: int, actor: dict = Depends(require_workspace)):
    if not get_candidate(candidate_id, user_id=actor["user_id"]):
        raise HTTPException(404, "Candidate profile not found")
    try:
        delete_candidate(candidate_id, user_id=actor["user_id"])
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.put("/api/search-jobs/{search_job_id}/candidate")
def map_candidate(search_job_id: int, payload: CandidateAssignmentPayload, actor: dict = Depends(require_workspace)):
    user_id = actor["user_id"]
    if not get_search_job(search_job_id, True, user_id=user_id):
        raise HTTPException(404, "Search job not found")
    if payload.candidate_profile_id and not get_candidate(payload.candidate_profile_id, user_id=user_id):
        raise HTTPException(404, "Candidate profile not found")
    assign_candidate(search_job_id, payload.candidate_profile_id, payload.enabled, user_id=user_id)
    return {"ok": True}


@app.get("/api/search-jobs/{search_job_id}/candidate")
def get_search_job_candidate(search_job_id: int, actor: dict = Depends(require_workspace)):
    if not get_search_job(search_job_id, True, user_id=actor["user_id"]):
        raise HTTPException(404, "Search job not found")
    return {"candidate": candidate_for_search_job(search_job_id, user_id=actor["user_id"])}


@app.get("/api/intelligence/settings")
def intelligence_settings(actor: dict = Depends(require_workspace)):
    user_id = actor["user_id"]
    return {
        "ollama_enabled": get_setting("intelligence_ollama_enabled", "false", user_id=user_id).lower()
        in ("1", "true", "yes", "on"),
        "ollama_url": get_setting("intelligence_ollama_url", "http://host.docker.internal:11434", user_id=user_id),
        "ollama_model": get_setting("intelligence_ollama_model", "gemma3", user_id=user_id),
        "ollama_timeout_seconds": int(get_setting("intelligence_ollama_timeout_seconds", "60", user_id=user_id) or 60),
        "deterministic_weight": 70,
        "ai_weight": 30,
        "engine": "hybrid-v2",
    }


@app.put("/api/intelligence/settings")
def update_intelligence_settings(payload: IntelligenceSettingsPayload, actor: dict = Depends(require_workspace)):
    user_id = actor["user_id"]
    set_setting("intelligence_ollama_enabled", str(payload.ollama_enabled).lower(), user_id=user_id)
    set_setting("intelligence_ollama_url", payload.ollama_url.strip(), user_id=user_id)
    set_setting("intelligence_ollama_model", payload.ollama_model.strip(), user_id=user_id)
    set_setting("intelligence_ollama_timeout_seconds", str(payload.ollama_timeout_seconds), user_id=user_id)
    return {"ok": True}


@app.post("/api/intelligence/analyze")
def analyze(payload: dict[str, Any], actor: dict = Depends(require_workspace)):
    try:
        return {
            "ok": True,
            "analysis": analyze_job(
                str(payload["job_key"]),
                int(payload["candidate_profile_id"]),
                payload.get("search_job_id"),
                bool(payload.get("force", False)),
                actor["user_id"],
            ),
        }
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/intelligence")
def intelligence(candidate_profile_id: int | None = None, limit: int = 300, actor: dict = Depends(require_workspace)):
    return {"analyses": list_analyses(candidate_profile_id, limit, user_id=actor["user_id"])}


@app.get("/api/intelligence/{candidate_profile_id}/{job_key:path}")
def intelligence_detail(candidate_profile_id: int, job_key: str, actor: dict = Depends(require_workspace)):
    data = get_analysis(job_key, candidate_profile_id, user_id=actor["user_id"])
    if not data:
        raise HTTPException(404, "Analysis not found")
    return data


@app.get("/api/v11-health")
def v11_health(_: str = Depends(require_admin)):
    return {
        "status": "ok",
        "version": "11.0.0",
        "candidate_profiles": len(list_candidates()),
        "analyses": len(list_analyses(limit=10000)),
    }
