import logging
import re
import threading
from collections import deque
from datetime import datetime, timezone

_MAX_LOGS = 2000
_lock = threading.Lock()
_entries = deque(maxlen=_MAX_LOGS)
_next_id = 1
_installed = False

_SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_ -]?key|token|password|secret|authorization)(\s*[=:]\s*)([^\s,;]+)'),
    re.compile(r'(?i)(key|token|api_key)=([^&\s]+)'),
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+\-/]+=*'),
]


def redact_log_text(value) -> str:
    text = str(value or '')
    text = _SECRET_PATTERNS[0].sub(lambda m: f'{m.group(1)}{m.group(2)}***', text)
    text = _SECRET_PATTERNS[1].sub(lambda m: f'{m.group(1)}=***', text)
    text = _SECRET_PATTERNS[2].sub(lambda m: f'{m.group(1)}***', text)
    return text[:12000]


class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        global _next_id
        try:
            message = redact_log_text(self.format(record))
            item = {
                'id': 0,
                'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': message,
            }
            with _lock:
                item['id'] = _next_id
                _next_id += 1
                _entries.append(item)
        except Exception:
            self.handleError(record)


def install_log_capture() -> None:
    global _installed
    if _installed:
        return
    handler = MemoryLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))
    # Uvicorn config can disable root propagation, so attach to its loggers too.
    for name in ('', 'uvicorn', 'uvicorn.error', 'uvicorn.access', 'jobtrack'):
        logger = logging.getLogger(name)
        if not any(isinstance(h, MemoryLogHandler) for h in logger.handlers):
            logger.addHandler(handler)
    _installed = True
    logging.getLogger('jobtrack.logs').info('Web log capture started')


def list_logs(limit: int = 300, level: str = '', query: str = '', after_id: int = 0) -> list[dict]:
    level = (level or '').upper().strip()
    query = (query or '').lower().strip()
    with _lock:
        rows = list(_entries)
    if after_id:
        rows = [r for r in rows if r['id'] > after_id]
    if level:
        wanted = logging._nameToLevel.get(level, 0)
        if wanted:
            rows = [r for r in rows if logging._nameToLevel.get(r['level'], 0) >= wanted]
    if query:
        rows = [r for r in rows if query in f"{r['logger']} {r['message']}".lower()]
    return rows[-max(1, min(int(limit), 1000)):]


def clear_logs() -> int:
    with _lock:
        count = len(_entries)
        _entries.clear()
    return count


def log_stats() -> dict:
    with _lock:
        rows = list(_entries)
    levels = {}
    for row in rows:
        levels[row['level']] = levels.get(row['level'], 0) + 1
    return {'stored': len(rows), 'capacity': _MAX_LOGS, 'levels': levels, 'latest_id': rows[-1]['id'] if rows else 0}
