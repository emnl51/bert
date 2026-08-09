from fastapi.testclient import TestClient

from app import db, system_mail
from app.config import settings
from app.security import _blocked_ips, _failed_attempts
from app.v16_main import app


def setup_system_email(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "system-email.db"))
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    monkeypatch.setattr(settings, "app_secret_key", "test-secret-key-with-sufficient-length")
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "correct-admin-password")
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(settings, "system_smtp_host", "")
    monkeypatch.setattr(settings, "system_smtp_username", "")
    monkeypatch.setattr(settings, "system_smtp_password", "")
    monkeypatch.setattr(settings, "system_email_from", "")
    _blocked_ips.clear()
    _failed_attempts.clear()
    db.init_db()


def admin_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/auth/admin-login",
        json={"username": "admin", "password": "correct-admin-password"},
    )
    assert response.status_code == 200
    return client


def test_system_email_api_is_admin_only(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)
    anonymous = TestClient(app)

    assert anonymous.get("/api/admin/system-email").status_code == 401
    assert anonymous.put("/api/admin/system-email", json={}).status_code == 401
    assert anonymous.post("/api/admin/system-email/test", json={"email": "a@example.com"}).status_code == 401
    assert anonymous.get("/system-email-ui.js").status_code == 401


def test_admin_can_save_system_email_without_exposing_password(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)
    client = admin_client()
    payload = {
        "public_base_url": "https://bert.example.com/",
        "registration_lifetime_hours": 36,
        "system_smtp_host": "smtp.gmail.com",
        "system_smtp_port": 587,
        "system_smtp_username": "bert@example.com",
        "system_smtp_password": "gmail-app-password",
        "system_smtp_use_tls": True,
        "system_email_from": "bert@example.com",
    }

    saved = client.put("/api/admin/system-email", json=payload)
    visible = client.get("/api/admin/system-email")

    assert saved.status_code == 200
    assert saved.json()["configured"] is True
    assert visible.status_code == 200
    assert visible.json()["public_base_url"] == "https://bert.example.com"
    assert visible.json()["registration_lifetime_hours"] == 36
    assert visible.json()["system_smtp_password"] == "configured"
    assert "gmail-app-password" not in visible.text
    assert db.get_setting("system_smtp_password") == "gmail-app-password"
    with db.connection() as con:
        stored = con.execute("SELECT value,is_secret FROM app_settings WHERE key='system_smtp_password'").fetchone()
    assert stored["is_secret"] == 1
    assert "gmail-app-password" not in stored["value"]


def test_blank_password_keeps_existing_secret(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)
    client = admin_client()
    payload = {
        "public_base_url": "https://bert.example.com",
        "registration_lifetime_hours": 24,
        "system_smtp_host": "smtp.gmail.com",
        "system_smtp_port": 587,
        "system_smtp_username": "bert@example.com",
        "system_smtp_password": "first-secret",
        "system_smtp_use_tls": True,
        "system_email_from": "bert@example.com",
    }
    assert client.put("/api/admin/system-email", json=payload).status_code == 200
    payload["system_smtp_password"] = ""
    payload["system_smtp_port"] = 2525

    assert client.put("/api/admin/system-email", json=payload).status_code == 200
    assert db.get_setting("system_smtp_password") == "first-secret"
    assert client.get("/api/admin/system-email").json()["system_smtp_password"] == "configured"


def test_environment_values_are_fallback_until_saved(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "public_base_url", "https://environment.example.com")
    monkeypatch.setattr(settings, "system_smtp_host", "smtp.environment.example.com")
    monkeypatch.setattr(settings, "system_smtp_password", "environment-secret")
    monkeypatch.setattr(settings, "system_email_from", "system@environment.example.com")

    visible = admin_client().get("/api/admin/system-email").json()

    assert visible["public_base_url"] == "https://environment.example.com"
    assert visible["system_smtp_host"] == "smtp.environment.example.com"
    assert visible["system_smtp_password"] == "configured"
    assert visible["configured"] is True


def test_system_email_test_uses_saved_smtp_settings(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self):
            calls["starttls"] = True

        def login(self, username, password):
            calls.update(username=username, password=password)

        def send_message(self, message):
            calls["message"] = message

    monkeypatch.setattr(system_mail.smtplib, "SMTP", FakeSMTP)
    client = admin_client()
    payload = {
        "public_base_url": "https://bert.example.com",
        "registration_lifetime_hours": 24,
        "system_smtp_host": "smtp.gmail.com",
        "system_smtp_port": 587,
        "system_smtp_username": "bert@example.com",
        "system_smtp_password": "gmail-app-password",
        "system_smtp_use_tls": True,
        "system_email_from": "bert@example.com",
    }
    assert client.put("/api/admin/system-email", json=payload).status_code == 200

    response = client.post("/api/admin/system-email/test", json={"email": "admin@example.com"})

    assert response.status_code == 200
    assert calls["host"] == "smtp.gmail.com"
    assert calls["port"] == 587
    assert calls["starttls"] is True
    assert calls["username"] == "bert@example.com"
    assert calls["password"] == "gmail-app-password"
    assert calls["message"]["To"] == "admin@example.com"


def test_system_email_ui_is_loaded_only_for_admin(tmp_path, monkeypatch):
    setup_system_email(tmp_path, monkeypatch)

    admin_workspace = admin_client().get("/app")

    assert admin_workspace.status_code == 200
    assert '<script src="/system-email-ui.js"></script>' in admin_workspace.text
    script = admin_client().get("/system-email-ui.js")
    assert script.status_code == 200
    assert "System email" in script.text
    assert "system_smtp_password" in script.text
