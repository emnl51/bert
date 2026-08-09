from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import db, system_mail
from app.config import settings
from app.security import _blocked_ips, _failed_attempts
from app.user_store import (
    authenticate_user,
    create_registration,
    hash_password,
    list_accounts,
    registration_for_token,
    verify_password,
)
from app.v16_main import app


def setup_accounts(tmp_path, monkeypatch):
    path = str(tmp_path / "accounts.db")
    monkeypatch.setattr(settings, "database_path", path)
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    monkeypatch.setattr(settings, "app_secret_key", "test-secret-key-with-sufficient-length")
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "correct-admin-password")
    _blocked_ips.clear()
    _failed_attempts.clear()
    db.init_db()


def test_passwords_use_argon2id():
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("argon2id$")
    assert verify_password("correct horse battery staple", encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_public_registration_activation_and_user_session(tmp_path, monkeypatch):
    setup_accounts(tmp_path, monkeypatch)
    sent = {}
    monkeypatch.setattr(
        system_mail, "send_activation_email", lambda email, token: sent.update(email=email, token=token)
    )
    client = TestClient(app)

    requested = client.post("/auth/register", json={"email": "New.User@Example.com"})
    assert requested.status_code == 202
    assert requested.json()["message"] == "If this email can be registered, an activation link has been sent."
    assert sent["email"] == "new.user@example.com"
    assert registration_for_token(sent["token"])["email"] == "new.user@example.com"
    assert client.get(f"/activate?token={sent['token']}").status_code == 200

    activated = client.post(
        "/auth/activate",
        json={"token": sent["token"], "full_name": "New User", "password": "a-secure-password-123"},
    )
    assert activated.status_code == 200
    assert activated.json()["redirect"] == "/account"
    assert client.get("/account").status_code == 200
    assert "New User" in client.get("/account").text
    assert client.get("/app").status_code == 401
    assert registration_for_token(sent["token"]) is None


def test_existing_email_returns_same_registration_response(tmp_path, monkeypatch):
    setup_accounts(tmp_path, monkeypatch)
    tokens = []
    monkeypatch.setattr(system_mail, "send_activation_email", lambda email, token: tokens.append(token))
    client = TestClient(app)
    client.post("/auth/register", json={"email": "same@example.com"})
    client.post(
        "/auth/activate",
        json={"token": tokens[0], "full_name": "Same User", "password": "a-secure-password-123"},
    )
    client.post("/auth/logout")

    repeated = client.post("/auth/register", json={"email": "same@example.com"})

    assert repeated.status_code == 202
    assert repeated.json()["message"] == "If this email can be registered, an activation link has been sent."
    assert len(tokens) == 1


def test_registration_resend_is_throttled_without_revealing_it(tmp_path, monkeypatch):
    setup_accounts(tmp_path, monkeypatch)
    tokens = []
    monkeypatch.setattr(system_mail, "send_activation_email", lambda email, token: tokens.append(token))
    client = TestClient(app)

    first = client.post("/auth/register", json={"email": "pending@example.com"})
    second = client.post("/auth/register", json={"email": "pending@example.com"})

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert len(tokens) == 1


def test_expired_registration_cannot_be_completed(tmp_path, monkeypatch):
    setup_accounts(tmp_path, monkeypatch)
    registration_id, token = create_registration("expired@example.com", "test", lifetime_hours=1)
    assert registration_id > 0
    with db.connection() as con:
        con.execute(
            "UPDATE user_registrations SET expires_at=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), registration_id),
        )
    client = TestClient(app)

    response = client.post(
        "/auth/activate",
        json={"token": token, "full_name": "Expired User", "password": "a-secure-password-123"},
    )

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_admin_can_disable_user_and_revoke_sessions(tmp_path, monkeypatch):
    setup_accounts(tmp_path, monkeypatch)
    sent = {}
    monkeypatch.setattr(system_mail, "send_activation_email", lambda email, token: sent.update(token=token))
    user_client = TestClient(app)
    user_client.post("/auth/register", json={"email": "member@example.com"})
    user_client.post(
        "/auth/activate",
        json={"token": sent["token"], "full_name": "Member User", "password": "a-secure-password-123"},
    )
    user_id = list_accounts()["users"][0]["id"]

    admin_client = TestClient(app)
    assert (
        admin_client.post(
            "/auth/admin-login", json={"username": "admin", "password": "correct-admin-password"}
        ).status_code
        == 200
    )
    disabled = admin_client.put(f"/api/admin/users/{user_id}/status", json={"status": "disabled"})

    assert disabled.status_code == 200
    assert user_client.get("/account").status_code == 401
    assert authenticate_user("member@example.com", "a-secure-password-123") is None


def test_registration_page_contains_working_user_forms():
    text = open("app/templates/login.html", encoding="utf-8").read()

    assert 'id="userForm"' in text
    assert 'id="registerForm"' in text
    assert "fetch('/auth/register'" in text
    assert "fetch('/auth/user-login'" in text
    users_ui = open("app/users-ui.js", encoding="utf-8").read()
    assert "section.classList.add('active')" in users_ui
    assert "localStorage.setItem('jobtrack-tab','users')" in users_ui
