import base64
import binascii
import hashlib
import hmac
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

security = HTTPBasic(auto_error=False)
SESSION_COOKIE = "bert_session"

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


def _session_signature(value: str) -> str:
    return hmac.new(settings.app_secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_admin_session() -> str:
    expires_at = int(time.time()) + settings.session_lifetime_seconds
    value = f"admin|{settings.admin_username}|{expires_at}|{secrets.token_urlsafe(16)}"
    token = f"{value}|{_session_signature(value)}"
    return base64.urlsafe_b64encode(token.encode()).decode().rstrip("=")


def read_admin_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        padded = token + "=" * (-len(token) % 4)
        role, username, expires_at, nonce, signature = base64.urlsafe_b64decode(padded).decode().split("|", 4)
        value = f"{role}|{username}|{expires_at}|{nonce}"
        expired = int(expires_at) < int(time.time())
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if role != "admin" or username != settings.admin_username:
        return None
    if expired:
        return None
    if not secrets.compare_digest(signature, _session_signature(value)):
        return None
    return username


def authenticate_admin(request: Request, username: str, password: str) -> bool:
    ip = _client_ip(request)
    require_login_attempt_allowed(request)

    ok_user = secrets.compare_digest(username, settings.admin_username)
    ok_password = secrets.compare_digest(password, settings.admin_password)
    if not (ok_user and ok_password):
        _record_auth_failure(ip)
        return False

    _record_auth_success(ip)
    return True


def require_login_attempt_allowed(request: Request) -> None:
    ip = _client_ip(request)
    if _is_rate_blocked(ip):
        retry_after = int(_remaining_block_seconds(ip))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def record_login_failure(request: Request) -> None:
    _record_auth_failure(_client_ip(request))


def record_login_success(request: Request) -> None:
    _record_auth_success(_client_ip(request))


def current_admin(request: Request) -> str | None:
    return read_admin_session(request.cookies.get(SESSION_COOKIE))


def current_user(request: Request) -> dict | None:
    if current_admin(request):
        return None
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    from .user_store import read_user_session

    return read_user_session(token)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_workspace(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> dict:
    """Return the authenticated workspace owner without trusting request data.

    The environment-backed administrator owns legacy rows, represented by a
    NULL user_id. Registered accounts always use their database user id.
    """
    admin = current_admin(request)
    if admin:
        return {"kind": "admin", "user_id": None, "name": admin, "role": "admin"}
    if credentials and authenticate_admin(request, credentials.username, credentials.password):
        return {"kind": "admin", "user_id": None, "name": credentials.username, "role": "admin"}
    user = current_user(request)
    if user:
        return {"kind": "user", "user_id": int(user["id"]), "name": user["email"], "role": user["role"]}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_admin(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
    session_user = current_admin(request)
    if session_user:
        return session_user

    if credentials and authenticate_admin(request, credentials.username, credentials.password):
        return credentials.username

    if credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_same_origin(request: Request) -> None:
    """Reject cross-site state-changing requests.

    Session cookies and Basic Auth credentials can be attached automatically.
    Requiring a same-origin fetch prevents a third-party page from turning an
    authenticated browser into a mutation trigger.
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
    Non-browser clients without these headers are allowed; authentication is
    still enforced by each protected route.
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
