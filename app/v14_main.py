from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from starlette.requests import Request

from . import v13_main as v13
from . import v10_main as v10
from .config import settings
from .database_admin import RESET_SCOPES, database_counts, list_user_tables, reset_database
from .security import require_admin

app = v13.app
app.version = '14.0.0'

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
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


@app.get('/database-ui.js')
def database_ui(_: str = Depends(require_admin)):
    return Response(Path('app/database-ui.js').read_text(encoding='utf-8'), media_type='application/javascript')


class ResetPayload(BaseModel):
    scope: str
    confirmation: str
    create_backup: bool = True


@app.get('/api/database/status')
def database_status(_: str = Depends(require_admin)):
    counts = database_counts()
    return {
        'version': '14.0.0',
        'database_path': settings.database_path,
        'tables': len(list_user_tables()),
        'counts': counts,
        'scopes': {**{k: v['label'] for k, v in RESET_SCOPES.items()}, 'operational': 'All Operational Data', 'factory': 'Factory Reset'},
    }


@app.post('/api/database/reset')
def database_reset(payload: ResetPayload, _: str = Depends(require_admin)):
    phrase = 'FACTORY RESET JOBTRACK' if payload.scope == 'factory' else 'RESET JOBTRACK'
    if payload.confirmation.strip() != phrase:
        raise HTTPException(400, f'Confirmation must exactly match: {phrase}')
    try:
        result = reset_database(payload.scope, create_backup=True if payload.scope == 'factory' else payload.create_backup)
        if payload.scope == 'factory':
            v10.reschedule_search_jobs()
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/v14-health')
def v14_health(_: str = Depends(require_admin)):
    return {'status': 'ok', 'version': '14.0.0', 'database_admin': True}
