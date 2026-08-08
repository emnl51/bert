from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from starlette.requests import Request

from . import v11_main as v11
from . import jobspy_provider  # noqa: F401 - registers the provider
from .config import settings
from .db import list_sources, save_source
from .security import require_admin

app = v11.app
app.version = '12.0.0'

# Replace only the dashboard route so the optional JobSpy UI can be loaded last.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/' and 'GET' in (getattr(r, 'methods', set()) or set()))
]


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_admin)):
    html = Path('app/templates/index.html').read_text(encoding='utf-8').replace('{{ app_name }}', settings.app_name)
    scripts = (
        '<script src="/language-ui.js"></script>'
        '<script src="/source-ui.js"></script>'
        '<script src="/review-ui.js"></script>'
        '<script src="/profile-ui.js"></script>'
        '<script src="/search-job-ui.js"></script>'
        '<script src="/intelligence-ui.js"></script>'
        '<script src="/intelligence-settings-ui.js"></script>'
        '<script src="/jobspy-ui.js"></script>'
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


@app.get('/jobspy-ui.js')
def jobspy_ui(_: str = Depends(require_admin)):
    return Response(Path('app/jobspy-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


class JobSpyPayload(BaseModel):
    name: str = Field(default='JobSpy Multi-board', min_length=1, max_length=100)
    enabled: bool = False
    sites: list[Literal['linkedin', 'indeed', 'google', 'glassdoor']] = ['linkedin', 'indeed', 'google']
    results_per_term: int = Field(default=20, ge=1, le=100)
    hours_old: int = Field(default=168, ge=1, le=720)
    max_search_terms: int = Field(default=6, ge=1, le=20)
    linkedin_fetch_description: bool = False


@app.get('/api/jobspy/source')
def get_jobspy_source(_: str = Depends(require_admin)):
    src = next((s for s in list_sources(mask_secrets=True) if s['source_type'] == 'jobspy'), None)
    return {'source': src}


@app.put('/api/jobspy/source')
def configure_jobspy(payload: JobSpyPayload, _: str = Depends(require_admin)):
    if not payload.sites:
        raise HTTPException(400, 'Select at least one JobSpy site')
    current = next((s for s in list_sources(mask_secrets=False) if s['source_type'] == 'jobspy'), None)
    config = {
        'sites': payload.sites,
        'results_per_term': payload.results_per_term,
        'hours_old': payload.hours_old,
        'max_search_terms': payload.max_search_terms,
        'linkedin_fetch_description': payload.linkedin_fetch_description,
    }
    source_id = save_source(
        payload.name,
        'jobspy',
        payload.enabled,
        config,
        {},
        source_id=current['id'] if current else None,
    )
    return {'ok': True, 'id': source_id, 'enabled': payload.enabled, 'config': config}


@app.get('/api/v12-health')
def v12_health(_: str = Depends(require_admin)):
    src = next((s for s in list_sources(mask_secrets=True) if s['source_type'] == 'jobspy'), None)
    return {'status': 'ok', 'version': '12.0.0', 'jobspy_configured': bool(src), 'jobspy_enabled': bool(src and src['enabled'])}
