import secrets
import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import settings

security = HTTPBasic()

# In-memory rate limiter for failed authentication attempts. Tracks per client
# IP and temporarily blocks after too many failures. Resets on successful auth.
_MAX_FAILED_ATTEMPTS = 5
_WINDOW_SECONDS = 900
_BLOCK_SECONDS = 900

_failed_attempts: dict[str, list[float]] = defaultdict(list)
_blocked_ips: dict[str, float] = {}
_rate_lock = Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_rate_blocked(ip: str) -> bool:
    with _rate_lock:
        blocked_until = _blocked_ips.get(ip)
        if blocked_until and time.monotonic() < blocked_until:
            return True
        if blocked_until:
            del _blocked_ips[ip]
        return False


def _record_auth_failure(ip: str) -> None:
    with _rate_lock:
        now = time.monotonic()
        attempts = [t for t in _failed_attempts[ip] if now - t < _WINDOW_SECONDS]
        attempts.append(now)
        _failed_attempts[ip] = attempts
        if len(attempts) >= _MAX_FAILED_ATTEMPTS:
            _blocked_ips[ip] = now + _BLOCK_SECONDS
            _failed_attempts[ip] = []


def _record_auth_success(ip: str) -> None:
    with _rate_lock:
        _failed_attempts.pop(ip, None)
        _blocked_ips.pop(ip, None)


def _remaining_block_seconds(ip: str) -> float:
    with _rate_lock:
        blocked_until = _blocked_ips.get(ip)
        if not blocked_until:
            return 0.0
        remaining = blocked_until - time.monotonic()
        if remaining <= 0:
            del _blocked_ips[ip]
            return 0.0
        return remaining


def require_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)) -> str:
    ip = _client_ip(request)

    if _is_rate_blocked(ip):
        retry_after = int(_remaining_block_seconds(ip))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    ok_user = secrets.compare_digest(credentials.username, settings.admin_username)
    ok_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (ok_user and ok_password):
        _record_auth_failure(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    _record_auth_success(ip)
    return credentials.username


def require_same_origin(request: Request) -> None:
    """Reject cross-site state-changing requests.

    Basic Auth credentials are attached by browsers automatically. Requiring
    a same-origin fetch prevents a third-party page from turning an authenticated
    browser into a mutation trigger. Non-browser clients (curl, etc.) without
    Sec-Fetch-Site/Origin headers are allowed through — Basic Auth protects them.
    """
    fetch_site = request.headers.get("sec-fetch-site", "")
    if fetch_site and fetch_site not in {"same-origin", "none"}:
        raise HTTPException(status_code=403, detail="Cross-site request rejected")

    origin = request.headers.get("origin")
    if origin:
        origin_parts = urlsplit(origin)
        if origin_parts.scheme not in {"http", "https"} or origin_parts.netloc != request.headers.get("host"):
            raise HTTPException(status_code=403, detail="Request origin does not match this server")


class CSRFMiddleware(BaseHTTPMiddleware):
    """Global CSRF protection for all state-changing HTTP methods.

    Checks Sec-Fetch-Site and Origin headers on POST/PUT/DELETE/PATCH requests.
    Same-origin browser fetches pass; cross-site form submissions are blocked.
    Non-browser clients without these headers are allowed (Basic Auth is their gate).
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next):
        if request.method not in self.SAFE_METHODS:
            fetch_site = request.headers.get("sec-fetch-site", "")
            if fetch_site and fetch_site not in {"same-origin", "none"}:
                return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)

            origin = request.headers.get("origin")
            if origin:
                origin_parts = urlsplit(origin)
                if origin_parts.scheme not in {"http", "https"} or origin_parts.netloc != request.headers.get("host"):
                    return JSONResponse({"detail": "Request origin does not match this server"}, status_code=403)

        return await call_next(request)
