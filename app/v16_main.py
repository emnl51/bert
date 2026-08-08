from pathlib import Path

from fastapi import Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from starlette.requests import Request

from . import v15_main as v15
from .config import settings
from .db import list_sources, save_source
from .security import require_admin

VERSION = '16.4.0'
app = v15.app
app.version = VERSION

# Replace the inherited dashboard and public health routes so the active shell and
# monitoring endpoint always report the current release instead of an older base layer.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        getattr(r, 'path', None) in {'/', '/health'}
        and 'GET' in (getattr(r, 'methods', set()) or set())
    )
]


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request, _: str = Depends(require_admin)):
    html = Path('app/templates/index.html').read_text(encoding='utf-8').replace('{{ app_name }}', settings.app_name)
    html = html.replace(
        'Supply Chain Tracker<small>Berlin / Brandenburg · v3</small>',
        f'JobTrack<small>Smart Job Search · v{VERSION}</small>',
    )
    scripts = (
        '<script src="/language-ui.js"></script>'
        '<script src="/source-ui.js"></script>'
        '<script src="/stepstone-ui.js"></script>'
        '<script src="/review-ui.js"></script>'
        '<script src="/legacy-compat-ui.js"></script>'
        '<script src="/profile-ui.js"></script>'
        '<script src="/search-job-ui.js"></script>'
        '<script src="/intelligence-ui.js"></script>'
        '<script src="/intelligence-settings-ui.js"></script>'
        '<script src="/jobspy-ui.js"></script>'
        '<script src="/source-analytics-ui.js"></script>'
        '<script src="/database-ui.js"></script>'
        '<script src="/log-ui.js"></script>'
        '<script src="/ui-shell.js"></script>'
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


@app.get('/health')
def health():
    return {'status': 'ok', 'version': app.version}


@app.get('/stepstone-ui.js')
def stepstone_ui(_: str = Depends(require_admin)):
    return Response(Path('app/stepstone-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


class StepStonePayload(BaseModel):
    name: str = Field(default='StepStone Germany', min_length=1, max_length=100)
    enabled: bool = False
    max_search_terms: int = Field(default=3, ge=1, le=10)
    pages_per_term: int = Field(default=1, ge=1, le=3)
    results_per_term: int = Field(default=25, ge=1, le=75)
    timeout_seconds: int = Field(default=30, ge=10, le=90)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=5)


@app.get('/api/stepstone/source')
def get_stepstone_source(_: str = Depends(require_admin)):
    source = next((s for s in list_sources(mask_secrets=True) if s['source_type'] == 'stepstone'), None)
    return {'source': source}


@app.put('/api/stepstone/source')
def configure_stepstone(payload: StepStonePayload, _: str = Depends(require_admin)):
    current = next((s for s in list_sources(mask_secrets=False) if s['source_type'] == 'stepstone'), None)
    config = {
        'max_search_terms': payload.max_search_terms,
        'pages_per_term': payload.pages_per_term,
        'results_per_term': payload.results_per_term,
        'timeout_seconds': payload.timeout_seconds,
        'request_delay_seconds': payload.request_delay_seconds,
    }
    source_id = save_source(
        payload.name,
        'stepstone',
        payload.enabled,
        config,
        {},
        source_id=current['id'] if current else None,
    )
    return {'ok': True, 'id': source_id, 'enabled': payload.enabled, 'config': config}


@app.get('/legacy-compat-ui.js')
def legacy_compat_ui(_: str = Depends(require_admin)):
    return Response(Path('app/legacy-compat-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


@app.get('/ui-shell.js')
def ui_shell(_: str = Depends(require_admin)):
    return Response(Path('app/ui-shell.js').read_text(encoding='utf-8'), media_type='application/javascript')


_FAVICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#2563eb"/><path d="M17 18h30v8H36v24h-9V26H17z" fill="white"/>
</svg>'''


@app.get('/favicon.svg', include_in_schema=False)
def favicon_svg():
    return Response(_FAVICON, media_type='image/svg+xml', headers={'Cache-Control': 'public, max-age=86400'})


@app.get('/favicon.ico', include_in_schema=False)
def favicon_ico():
    return Response(_FAVICON, media_type='image/svg+xml', headers={'Cache-Control': 'public, max-age=86400'})


@app.get('/apple-touch-icon.png', include_in_schema=False)
@app.get('/apple-touch-icon-precomposed.png', include_in_schema=False)
def apple_touch_icon():
    return Response(status_code=204, headers={'Cache-Control': 'public, max-age=86400'})


@app.get('/api/v16-health')
def v16_health(_: str = Depends(require_admin)):
    return {
        'status': 'ok',
        'version': app.version,
        'responsive_ui': True,
        'mobile_navigation': True,
        'mobile_tables': True,
        'reset_refresh_fix': True,
        'employment_format_filter': True,
        'legacy_jobs_refresh_fix': True,
        'stepstone_experimental_provider': True,
        'hybrid_cv_intelligence': True,
        'evidence_based_cv_match': True,
        'ollama_context_weight': 30,
        'intelligence_cache': True,
    }
