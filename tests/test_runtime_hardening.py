import sqlite3

import pytest

from app import db
from app.config import settings, validate_secure_settings
from app.profile_store import ensure_profile_schema
from app.search_job_store import (
    acquire_search_job_lock,
    ensure_search_job_schema,
    list_search_jobs,
    release_search_job_lock,
)


def test_published_credentials_are_rejected(monkeypatch):
    for password, secret in (
        ("change-me", "change-this-secret-key"),
        ("replace-with-a-long-unique-password", "replace-with-at-least-32-random-characters"),
    ):
        monkeypatch.setattr(settings, "admin_password", password)
        monkeypatch.setattr(settings, "app_secret_key", secret)
        with pytest.raises(RuntimeError, match="Insecure default configuration"):
            validate_secure_settings()


def test_database_connections_enable_safety_pragmas(tmp_path, monkeypatch):
    path = tmp_path / "jobs.db"
    monkeypatch.setattr(db.settings, "database_path", str(path))
    db.init_db()
    with db.connection() as con:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_search_job_lease_prevents_duplicate_worker_run(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_profile_schema()
    ensure_search_job_schema()
    job_id = list_search_jobs()[0]["id"]

    assert acquire_search_job_lock(job_id, "worker-a")
    assert not acquire_search_job_lock(job_id, "worker-b")
    release_search_job_lock(job_id, "worker-a")
    assert acquire_search_job_lock(job_id, "worker-b")

    with sqlite3.connect(db.settings.database_path) as con:
        assert con.execute("SELECT owner FROM search_job_locks").fetchone()[0] == "worker-b"
