from pathlib import Path

from fastapi import Depends
from fastapi.responses import HTMLResponse, Response
from starlette.requests import Request

from . import v15_main as v15
from .config import settings
from .security import require_admin

app = v15.app
app.version = '16.2.0'

# Replace only the dashboard route so the responsive shell loads after all feature UIs.
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
        '<script src="/source-analytics-ui.js"></script>'
        '<script src="/database-ui.js"></script>'
        '<script src="/log-ui.js"></script>'
        '<script src="/ui-shell.js"></script>'
    )
    return HTMLResponse(html.replace('</body>', scripts + '</body>'))


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
    # Avoid noisy browser-generated 404s without adding a binary asset to the image.
    return Response(status_code=204, headers={'Cache-Control': 'public, max-age=86400'})


@app.get('/api/v16-health')
def v16_health(_: str = Depends(require_admin)):
    return {
        'status': 'ok',
        'version': '16.2.0',
        'responsive_ui': True,
        'mobile_navigation': True,
        'mobile_tables': True,
        'reset_refresh_fix': True,
        'employment_format_filter': True,
    }
