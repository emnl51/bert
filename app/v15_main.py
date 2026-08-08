from pathlib import Path

from fastapi import Depends, Query
from fastapi.responses import HTMLResponse, Response
from starlette.requests import Request

from . import v14_main as v14
from .config import settings
from .log_store import clear_logs, install_log_capture, list_logs, log_stats
from .security import require_admin

app = v14.app
app.version = '15.0.0'
install_log_capture()

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
        '<script src="/database-ui.js"></script>'
        '<script src="/log-ui.js"></script>'
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


@app.get('/log-ui.js')
def log_ui(_: str = Depends(require_admin)):
    return Response(Path('app/log-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


@app.get('/api/logs')
def api_logs(
    limit: int = Query(300, ge=1, le=1000),
    level: str = Query('', max_length=20),
    q: str = Query('', max_length=200),
    after_id: int = Query(0, ge=0),
    _: str = Depends(require_admin),
):
    return {'logs': list_logs(limit=limit, level=level, query=q, after_id=after_id), 'stats': log_stats()}


@app.delete('/api/logs')
def api_clear_logs(_: str = Depends(require_admin)):
    return {'ok': True, 'cleared': clear_logs()}


@app.get('/api/v15-health')
def v15_health(_: str = Depends(require_admin)):
    return {'status': 'ok', 'version': '15.0.0', 'web_logs': True, 'log_stats': log_stats()}
