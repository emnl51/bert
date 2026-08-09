from fastapi.testclient import TestClient

from app.config import settings
from app.security import _blocked_ips, _failed_attempts, create_admin_session, read_admin_session
from app.v16_main import app


def _reset_rate_limit():
    _blocked_ips.clear()
    _failed_attempts.clear()


def test_entry_page_has_all_three_access_options(monkeypatch):
    monkeypatch.setattr(settings, "app_name", "Bert")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Administrator" in response.text
    assert "Registered user" in response.text
    assert "New user" in response.text
    assert "Send activation link" in response.text
    assert "administrator will invite" not in response.text.lower()


def test_admin_form_creates_session_and_opens_dashboard(monkeypatch):
    _reset_rate_limit()
    monkeypatch.setattr(settings, "admin_username", "admin@example.test")
    monkeypatch.setattr(settings, "admin_password", "correct-password")
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    client = TestClient(app)

    protected = client.get("/app")
    assert protected.status_code == 401
    assert "WWW-Authenticate" not in protected.headers

    login = client.post(
        "/auth/admin-login",
        json={"username": "admin@example.test", "password": "correct-password"},
    )
    assert login.status_code == 200
    assert login.json()["redirect"] == "/app"
    assert "httponly" in login.headers["set-cookie"].lower()
    assert client.get("/app").status_code == 200

    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert client.get("/app").status_code == 401


def test_admin_form_rejects_invalid_credentials(monkeypatch):
    _reset_rate_limit()
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "correct-password")
    client = TestClient(app)

    response = client.post("/auth/admin-login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_admin_session_rejects_tampering_and_malformed_expiry(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "app_secret_key", "a-test-secret-that-is-long-enough")
    token = create_admin_session()

    assert read_admin_session(token) == "admin"
    assert read_admin_session(token[:-1] + ("A" if token[-1] != "A" else "B")) is None
    assert read_admin_session("YWRtaW58YWRtaW58bm90LWEtbnVtYmVyfG5vbmNlfHNpZw") is None
    assert read_admin_session("%%%") is None
