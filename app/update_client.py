"""Narrow client for the optional host-side update agent."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from .config import settings


class UpdateAgentError(RuntimeError):
    """Raised when the host update agent cannot complete a request."""


def _disabled_status() -> dict:
    return {
        "configured": False,
        "state": "disabled",
        "message": "The host update agent is not configured.",
        "update_available": False,
    }


def _agent_request(method: str, path: str, *, timeout: float | None = None) -> dict:
    socket_path = settings.update_agent_socket.strip()
    token = settings.update_agent_token.strip()
    if not socket_path or not token:
        return _disabled_status()

    transport = httpx.HTTPTransport(uds=socket_path)
    headers = {"Authorization": f"Bearer {token}"}
    request_timeout = timeout if timeout is not None else settings.update_agent_timeout_seconds
    try:
        with httpx.Client(transport=transport, base_url="http://jobtrack-updater", timeout=request_timeout) as client:
            response = client.request(method, path, headers=headers)
            if response.is_error:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise UpdateAgentError(f"Update agent rejected the request: {detail or response.reason_phrase}")
            response.raise_for_status()
            payload = response.json()
    except UpdateAgentError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise UpdateAgentError(f"Update agent is unavailable: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateAgentError("Update agent returned an invalid response.")
    payload["configured"] = True
    return payload


def update_status() -> dict:
    return _agent_request("GET", "/v1/status")


def check_for_updates() -> dict:
    return _agent_request("POST", "/v1/check", timeout=30.0)


def start_update() -> dict:
    return _agent_request("POST", "/v1/update", timeout=10.0)


def require_same_origin_update(request: Request) -> None:
    """Reject cross-site state-changing update requests.

    Basic Auth credentials can be attached by a browser automatically. Requiring
    a same-origin fetch plus a non-simple custom header prevents a third-party
    page from turning an authenticated browser into a deploy trigger.
    """

    if request.headers.get("x-jobtrack-action") != "update":
        raise HTTPException(status_code=403, detail="Missing update action header")

    fetch_site = request.headers.get("sec-fetch-site", "")
    if fetch_site and fetch_site not in {"same-origin", "none"}:
        raise HTTPException(status_code=403, detail="Cross-site update request rejected")

    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=403, detail="Missing request origin")
    origin_parts = urlsplit(origin)
    if origin_parts.scheme not in {"http", "https"} or origin_parts.netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Request origin does not match this server")
