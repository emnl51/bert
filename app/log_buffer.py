import logging
import re
import threading
from collections import deque
from datetime import datetime, timezone

MAX_LOGS = 2000
_lock = threading.Lock()
_entries = deque(maxlen=MAX_LOGS)
_seq = 0

SECRET_PATTERNS = [
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+"), r"\1***"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)(=|:|\s+)[^&\s,;]+"), r"\1\2***"),
    (re.compile(r"(https?://jooble\.org/api/)[^\s\'\"]+"), r"\1***"),
]


def _sanitize(text: str) -> str:
    out = str(text or "")
    for pattern, repl in SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out[:5000]


def _ignore_message(message: str) -> bool:
    lowered = message.lower()
    return any(x in lowered for x in ("/api/logs", "/health", "/log-ui.js", "/favicon.ico", "/apple-touch-icon"))


class MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _seq
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + self.formatException(record.exc_info) if hasattr(self, "formatException") else ""
            message = _sanitize(message)
            if _ignore_message(message):
                return
            with _lock:
                _seq += 1
                _entries.append(
                    {
                        "seq": _seq,
                        "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": message,
                    }
                )
        except Exception:
            pass


_handler = MemoryLogHandler(level=logging.INFO)
_handler.setFormatter(logging.Formatter("%(message)s"))
_installed = False


def install_log_buffer() -> None:
    global _installed
    if _installed:
        return
    targets = [
        logging.getLogger(),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("jobtrack"),
    ]
    for logger in targets:
        if not any(isinstance(h, MemoryLogHandler) for h in logger.handlers):
            logger.addHandler(_handler)
    _installed = True


def list_logs(limit: int = 300, level: str = "ALL", query: str = "", logger_name: str = "") -> list[dict]:
    limit = max(1, min(int(limit), 2000))
    level = (level or "ALL").upper()
    q = (query or "").strip().lower()
    logger_filter = (logger_name or "").strip().lower()
    with _lock:
        rows = list(_entries)
    if level != "ALL":
        rows = [r for r in rows if r["level"].upper() == level]
    if logger_filter:
        rows = [r for r in rows if logger_filter in r["logger"].lower()]
    if q:
        rows = [r for r in rows if q in r["message"].lower() or q in r["logger"].lower()]
    return rows[-limit:]


def clear_logs() -> None:
    with _lock:
        _entries.clear()


def log_stats() -> dict:
    with _lock:
        rows = list(_entries)
    counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    for row in rows:
        level = row["level"].upper()
        counts[level] = counts.get(level, 0) + 1
    return {"total": len(rows), "max_entries": MAX_LOGS, "levels": counts}
