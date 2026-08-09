import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import db
from app.database_admin import (
    DatabaseRestoreBusy,
    DatabaseRestoreFailed,
    InvalidDatabaseBackup,
    backup_database,
    create_download_backup,
    remove_temporary_database,
    reset_database,
    restore_database,
    validate_database_backup,
)
from app.feedback_store import ensure_feedback_schema
from app.models import Job
from app.profile_store import ensure_profile_schema
from app.search_job_store import ensure_search_job_schema


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobtrack.db"))
    import app.database_admin as database_admin

    monkeypatch.setattr(database_admin.settings, "database_path", str(tmp_path / "jobtrack.db"))
    db.init_db()
    ensure_profile_schema()
    ensure_search_job_schema()
    ensure_feedback_schema()


def test_backup_database_creates_snapshot(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    path = backup_database()
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_download_backup_is_valid_and_removable(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    path, filename = create_download_backup()
    assert filename.startswith("jobtrack-data-")
    assert filename.endswith(".db")
    assert validate_database_backup(path)["integrity"] == "ok"
    remove_temporary_database(path)
    assert not Path(path).exists()


def test_restore_replaces_data_and_keeps_current_safety_backup(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    db.upsert_job(
        Job(
            source="test",
            external_id="backup",
            title="Saved job",
            company="Example",
            location="Berlin",
            url="https://example.com/backup",
        )
    )
    source_backup = backup_database()
    db.upsert_job(
        Job(
            source="test",
            external_id="newer",
            title="Newer job",
            company="Example",
            location="Berlin",
            url="https://example.com/newer",
        )
    )

    result = restore_database(source_backup)

    assert result["verified"] is True
    assert result["before"]["jobs"] == 2
    assert result["after"]["jobs"] == 1
    assert Path(result["safety_backup_path"]).exists()
    with db.connection() as con:
        titles = [row[0] for row in con.execute("SELECT title FROM jobs ORDER BY title").fetchall()]
    assert titles == ["Saved job"]


def test_invalid_restore_never_changes_current_database(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    db.upsert_job(
        Job(
            source="test",
            external_id="keep",
            title="Keep me",
            company="Example",
            location="Berlin",
            url="https://example.com/keep",
        )
    )
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"not a sqlite backup")

    with pytest.raises(InvalidDatabaseBackup, match="not a SQLite"):
        restore_database(invalid)

    with db.connection() as con:
        assert con.execute("SELECT title FROM jobs").fetchone()[0] == "Keep me"


def test_non_bert_sqlite_database_is_rejected(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    other = tmp_path / "other.db"
    with sqlite3.connect(other) as con:
        con.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")

    with pytest.raises(InvalidDatabaseBackup, match="not a Bert database"):
        restore_database(other)


def test_oversized_backup_is_rejected_before_restore(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    backup = Path(backup_database())
    import app.database_admin as database_admin

    monkeypatch.setattr(database_admin.settings, "database_restore_max_bytes", backup.stat().st_size - 1)

    with pytest.raises(InvalidDatabaseBackup, match="exceeds"):
        restore_database(backup)


def test_backup_with_foreign_key_errors_is_rejected(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    backup = backup_database()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(backup) as con:
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute(
            "INSERT INTO applications(job_key,status,notes,created_at,updated_at) VALUES(?,?,?,?,?)",
            ("missing-job", "to_apply", "", now, now),
        )

    with pytest.raises(InvalidDatabaseBackup, match="foreign-key"):
        restore_database(backup)


def test_failed_restore_migration_rolls_back_current_database(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    db.upsert_job(
        Job(
            source="test",
            external_id="old",
            title="Backup state",
            company="Example",
            location="Berlin",
            url="https://example.com/old",
        )
    )
    source_backup = backup_database()
    db.upsert_job(
        Job(
            source="test",
            external_id="current",
            title="Current state",
            company="Example",
            location="Berlin",
            url="https://example.com/current",
        )
    )
    import app.database_admin as database_admin

    monkeypatch.setattr(database_admin, "_reseed_factory_defaults", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(DatabaseRestoreFailed, match="previous database was restored"):
        restore_database(source_backup)

    with db.connection() as con:
        titles = {row[0] for row in con.execute("SELECT title FROM jobs").fetchall()}
    assert titles == {"Backup state", "Current state"}


def test_restore_is_blocked_while_search_job_is_running(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    ensure_search_job_schema()
    source_backup = backup_database()
    now = datetime.now(timezone.utc)
    with db.connection() as con:
        job_id = con.execute(
            "INSERT INTO search_jobs(name,profile_id,created_at,updated_at) VALUES(?,?,?,?)",
            ("Running search", 1, now.isoformat(), now.isoformat()),
        ).lastrowid
        con.execute(
            "INSERT INTO search_job_locks(search_job_id,owner,expires_at) VALUES(?,?,?)",
            (job_id, "test-owner", (now + timedelta(minutes=5)).isoformat()),
        )

    with pytest.raises(DatabaseRestoreBusy, match="search job"):
        restore_database(source_backup)


def test_operational_reset_preserves_configuration(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    job = Job(
        source="test",
        external_id="1",
        title="Supply Chain Working Student",
        company="Example",
        location="Berlin",
        url="https://example.com/1",
    )
    db.upsert_job(job)
    before_sources = len(db.list_sources())
    result = reset_database("operational", create_backup=True)
    assert result["verified"] is True
    assert result["remaining"] == {}
    assert result["after"]["jobs"] == 0
    assert result["rows_deleted"] >= 1
    with db.connection() as con:
        assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == before_sources
        assert con.execute("SELECT COUNT(*) FROM search_profiles").fetchone()[0] >= 1


def test_jobs_reset_reports_zero_jobs(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    for i in range(3):
        db.upsert_job(
            Job(
                source="test",
                external_id=str(i),
                title=f"Job {i}",
                company="Example",
                location="Berlin",
                url=f"https://example.com/{i}",
            )
        )
    result = reset_database("jobs", create_backup=False)
    assert result["verified"] is True
    assert result["before"]["jobs"] == 3
    assert result["after"]["jobs"] == 0
    assert result["deleted"]["jobs"] == 3


def test_factory_reset_reseeds_defaults(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    with db.connection() as con:
        con.execute("UPDATE sources SET name='Changed Source' WHERE id=(SELECT MIN(id) FROM sources)")
    result = reset_database("factory", create_backup=True)
    assert result["verified"] is True
    assert result["remaining"] == {}
    assert result["after"]["jobs"] == 0
    assert result["backup_path"]
    with db.connection() as con:
        assert con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] >= 1
        assert con.execute("SELECT COUNT(*) FROM search_profiles").fetchone()[0] >= 2
        assert con.execute("SELECT COUNT(*) FROM search_jobs").fetchone()[0] >= 1
