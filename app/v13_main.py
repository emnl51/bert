from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, Query
from fastapi.responses import HTMLResponse, Response
from starlette.requests import Request

from . import v12_main as v12
from .config import settings
from .security import require_admin
from .source_analytics import ensure_source_analytics_schema, list_source_run_stats, source_quality_summary
from .run_safety import scrub_run_history_secrets

app = v12.app
_original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def v13_lifespan(application):
    async with _original_lifespan(application):
        ensure_source_analytics_schema()
        scrub_run_history_secrets()
        yield


app.router.lifespan_context = v13_lifespan
app.version = '13.0.0'

app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/' and 'GET' in (getattr(r, 'methods', set()) or set()))]


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
        '<script src="/source-analytics-ui.js"></script>'
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


@app.get('/source-analytics-ui.js')
def source_analytics_ui(_: str = Depends(require_admin)):
    return Response(Path('app/source-analytics-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


@app.get('/api/source-analytics')
def source_analytics(last_runs: int = Query(20, ge=1, le=200), _: str = Depends(require_admin)):
    return {'summary': source_quality_summary(last_runs)}


@app.get('/api/source-analytics/runs')
def source_analytics_runs(run_id: int | None = None, limit: int = Query(200, ge=1, le=1000), _: str = Depends(require_admin)):
    return {'rows': list_source_run_stats(run_id=run_id, limit=limit)}


@app.get('/api/v13-health')
def v13_health(_: str = Depends(require_admin)):
    return {'status': 'ok', 'version': '13.0.0', 'source_analytics': True}
