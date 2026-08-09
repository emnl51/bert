import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from .config import settings
from .db import connection


USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin','user')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','disabled')),
    email_verified_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

CREATE TABLE IF NOT EXISTS user_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    completed_at TEXT,
    revoked_at TEXT,
    requested_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_registrations_email ON user_registrations(email);
CREATE INDEX IF NOT EXISTS idx_user_registrations_token ON user_registrations(token_hash);

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT,
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token_hash);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC);
"""

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_ARGON_MEMORY_KIB = 65_536
_ARGON_ITERATIONS = 3
_ARGON_LANES = 4


class AccountError(ValueError):
    pass


class RegistrationError(AccountError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.fullmatch(value):
        raise AccountError("Enter a valid email address")
    return value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def ensure_user_schema() -> None:
    with connection() as con:
        con.executescript(USER_SCHEMA)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise AccountError("Password must contain at least 12 characters")
    if len(password) > 1024:
        raise AccountError("Password is too long")
    salt = secrets.token_bytes(16)
    derived = Argon2id(
        salt=salt,
        length=32,
        iterations=_ARGON_ITERATIONS,
        lanes=_ARGON_LANES,
        memory_cost=_ARGON_MEMORY_KIB,
    ).derive(password.encode("utf-8"))
    return f"argon2id$m={_ARGON_MEMORY_KIB},t={_ARGON_ITERATIONS},p={_ARGON_LANES}${_encode(salt)}${_encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, params, salt_text, expected_text = encoded.split("$", 3)
        values = dict(item.split("=", 1) for item in params.split(","))
        if algorithm != "argon2id":
            return False
        salt = _decode(salt_text)
        expected = _decode(expected_text)
        actual = Argon2id(
            salt=salt,
            length=len(expected),
            iterations=int(values["t"]),
            lanes=int(values["p"]),
            memory_cost=int(values["m"]),
        ).derive(password.encode("utf-8"))
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, expected)


def record_audit(actor: str, action: str, target: str = "", details: dict[str, Any] | None = None) -> None:
    ensure_user_schema()
    with connection() as con:
        con.execute(
            "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
            (actor, action, target, json.dumps(details or {}, ensure_ascii=True), _iso()),
        )


def create_registration(email: str, requested_by: str, lifetime_hours: int | None = None) -> tuple[int, str] | None:
    ensure_user_schema()
    normalized = _normalize_email(email)
    now = _now()
    if lifetime_hours is None:
        from .system_mail import registration_lifetime_hours

        lifetime_hours = registration_lifetime_hours()
    expires = now + timedelta(hours=lifetime_hours)
    token = secrets.token_urlsafe(32)
    with connection() as con:
        existing = con.execute("SELECT id FROM users WHERE email=?", (normalized,)).fetchone()
        if existing:
            return None
        recent_for_email = con.execute(
            """SELECT 1 FROM user_registrations
               WHERE email=? AND created_at>? ORDER BY created_at DESC LIMIT 1""",
            (normalized, _iso(now - timedelta(minutes=2))),
        ).fetchone()
        recent_for_requester = con.execute(
            "SELECT COUNT(*) FROM user_registrations WHERE requested_by=? AND created_at>?",
            (requested_by, _iso(now - timedelta(hours=1))),
        ).fetchone()[0]
        if recent_for_email or recent_for_requester >= 5:
            return None
        con.execute(
            "UPDATE user_registrations SET revoked_at=? WHERE email=? AND completed_at IS NULL AND revoked_at IS NULL",
            (_iso(now), normalized),
        )
        cursor = con.execute(
            """INSERT INTO user_registrations
               (email,token_hash,expires_at,requested_by,created_at) VALUES(?,?,?,?,?)""",
            (normalized, _token_hash(token), _iso(expires), requested_by, _iso(now)),
        )
        registration_id = int(cursor.lastrowid)
        con.execute(
            "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
            (normalized, "user.registration_requested", normalized, "{}", _iso(now)),
        )
    return registration_id, token


def revoke_registration(registration_id: int, actor: str, action: str = "user.registration_revoked") -> bool:
    ensure_user_schema()
    now = _iso()
    with connection() as con:
        row = con.execute("SELECT email FROM user_registrations WHERE id=?", (registration_id,)).fetchone()
        if not row:
            return False
        changed = con.execute(
            "UPDATE user_registrations SET revoked_at=? WHERE id=? AND completed_at IS NULL AND revoked_at IS NULL",
            (now, registration_id),
        ).rowcount
        if changed:
            con.execute(
                "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
                (actor, action, row["email"], "{}", now),
            )
    return bool(changed)


def registration_for_token(token: str) -> dict[str, Any] | None:
    ensure_user_schema()
    if not token or len(token) > 256:
        return None
    with connection() as con:
        row = con.execute(
            """SELECT id,email,expires_at,completed_at,revoked_at
               FROM user_registrations WHERE token_hash=?""",
            (_token_hash(token),),
        ).fetchone()
    if not row or row["completed_at"] or row["revoked_at"] or row["expires_at"] <= _iso():
        return None
    return dict(row)


def complete_registration(token: str, full_name: str, password: str) -> dict[str, Any]:
    ensure_user_schema()
    name = " ".join(full_name.split())
    if len(name) < 2 or len(name) > 120:
        raise AccountError("Enter your full name")
    password_hash = hash_password(password)
    now = _iso()
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        registration = con.execute(
            """SELECT id,email,expires_at,completed_at,revoked_at
               FROM user_registrations WHERE token_hash=?""",
            (_token_hash(token),),
        ).fetchone()
        if not registration or registration["completed_at"] or registration["revoked_at"]:
            raise RegistrationError("This activation link is invalid or has already been used")
        if registration["expires_at"] <= now:
            raise RegistrationError("This activation link has expired")
        try:
            cursor = con.execute(
                """INSERT INTO users
                   (email,password_hash,full_name,role,status,email_verified_at,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    registration["email"],
                    password_hash,
                    name,
                    "user",
                    "active",
                    now,
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise RegistrationError("An account already exists for this email address") from exc
        con.execute("UPDATE user_registrations SET completed_at=? WHERE id=?", (now, registration["id"]))
        con.execute(
            "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
            (registration["email"], "user.activated", registration["email"], "{}", now),
        )
    return {"id": int(cursor.lastrowid), "email": registration["email"], "full_name": name, "role": "user"}


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    ensure_user_schema()
    try:
        normalized = _normalize_email(email)
    except AccountError:
        return None
    with connection() as con:
        row = con.execute(
            "SELECT id,email,password_hash,full_name,role,status FROM users WHERE email=?",
            (normalized,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    if row["status"] != "active":
        return None
    now = _iso()
    with connection() as con:
        con.execute("UPDATE users SET last_login_at=?,updated_at=? WHERE id=?", (now, now, row["id"]))
    return {key: row[key] for key in ("id", "email", "full_name", "role", "status")}


def create_user_session(user_id: int, ip_address: str = "", user_agent: str = "") -> str:
    ensure_user_schema()
    token = secrets.token_urlsafe(48)
    now = _now()
    expires = now + timedelta(seconds=settings.session_lifetime_seconds)
    with connection() as con:
        con.execute(
            """INSERT INTO user_sessions
               (user_id,token_hash,expires_at,created_at,last_seen_at,ip_address,user_agent)
               VALUES(?,?,?,?,?,?,?)""",
            (
                user_id,
                _token_hash(token),
                _iso(expires),
                _iso(now),
                _iso(now),
                ip_address[:64],
                user_agent[:300],
            ),
        )
    return token


def read_user_session(token: str | None) -> dict[str, Any] | None:
    ensure_user_schema()
    if not token or len(token) > 256:
        return None
    now = _iso()
    with connection() as con:
        row = con.execute(
            """SELECT s.id AS session_id,u.id,u.email,u.full_name,u.role,u.status,s.expires_at,s.revoked_at
               FROM user_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?""",
            (_token_hash(token),),
        ).fetchone()
        if not row or row["revoked_at"] or row["expires_at"] <= now or row["status"] != "active":
            return None
        con.execute("UPDATE user_sessions SET last_seen_at=? WHERE id=?", (now, row["session_id"]))
    return {key: row[key] for key in ("id", "email", "full_name", "role", "status", "session_id")}


def revoke_user_session(token: str | None) -> None:
    if not token:
        return
    ensure_user_schema()
    with connection() as con:
        con.execute(
            "UPDATE user_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
            (_iso(), _token_hash(token)),
        )


def list_accounts() -> dict[str, list[dict[str, Any]]]:
    ensure_user_schema()
    now = _iso()
    with connection() as con:
        users = [
            dict(row)
            for row in con.execute(
                """SELECT id,email,full_name,role,status,email_verified_at,created_at,last_login_at,
                   (SELECT COUNT(*) FROM user_sessions s WHERE s.user_id=users.id AND s.revoked_at IS NULL
                    AND s.expires_at>?) AS active_sessions
                   FROM users ORDER BY created_at DESC""",
                (now,),
            ).fetchall()
        ]
        registrations = [
            dict(row)
            for row in con.execute(
                """SELECT id,email,expires_at,completed_at,revoked_at,requested_by,created_at
                   FROM user_registrations ORDER BY created_at DESC LIMIT 100"""
            ).fetchall()
        ]
    for registration in registrations:
        if registration["completed_at"]:
            registration["state"] = "completed"
        elif registration["revoked_at"]:
            registration["state"] = "revoked"
        elif registration["expires_at"] <= now:
            registration["state"] = "expired"
        else:
            registration["state"] = "pending"
    return {"users": users, "registrations": registrations}


def set_user_status(user_id: int, status: str, actor: str) -> bool:
    ensure_user_schema()
    if status not in {"active", "disabled"}:
        raise AccountError("Invalid account status")
    now = _iso()
    with connection() as con:
        row = con.execute("SELECT email,status FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False
        con.execute("UPDATE users SET status=?,updated_at=? WHERE id=?", (status, now, user_id))
        if status == "disabled":
            con.execute("UPDATE user_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user_id))
        con.execute(
            "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
            (actor, f"user.{status}", row["email"], "{}", now),
        )
    return True


def revoke_all_user_sessions(user_id: int, actor: str) -> bool:
    ensure_user_schema()
    now = _iso()
    with connection() as con:
        row = con.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False
        con.execute("UPDATE user_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (now, user_id))
        con.execute(
            "INSERT INTO audit_events(actor,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
            (actor, "user.sessions_revoked", row["email"], "{}", now),
        )
    return True
