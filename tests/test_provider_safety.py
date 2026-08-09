import httpx
from app.providers import _safe_provider_error


def test_provider_error_redacts_secret_value():
    request = httpx.Request("POST", "https://jooble.org/api/super-secret-key")
    response = httpx.Response(403, request=request)
    exc = httpx.HTTPStatusError("403 for https://jooble.org/api/super-secret-key", request=request, response=response)
    source = {"secrets": {"api_key": "super-secret-key"}}
    message = _safe_provider_error(source, exc)
    assert "super-secret-key" not in message
    assert message.startswith("HTTP 403")
