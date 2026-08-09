from app import db
from app.models import Job


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    job = Job(
        source="Test",
        external_id="abc123",
        title="Werkstudent Supply Chain",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/job",
        score=80,
    )
    assert db.upsert_job(job) is True
    return job


def test_apply_decision_creates_tracker_and_maybe_removes_unsubmitted_queue(tmp_path, monkeypatch):
    job = setup_db(tmp_path, monkeypatch)

    db.set_job_decision(job.key, "apply")
    apps = db.list_applications()
    assert len(apps) == 1
    assert apps[0]["status"] == "to_apply"
    assert apps[0]["decision"] == "apply"

    db.set_job_decision(job.key, "maybe")
    assert db.list_applications() == []
    maybe_jobs = db.list_jobs(decision="maybe")
    assert maybe_jobs[0]["job_key"] == job.key


def test_application_progress_is_preserved_if_job_decision_changes(tmp_path, monkeypatch):
    job = setup_db(tmp_path, monkeypatch)
    db.set_job_decision(job.key, "apply")
    db.save_application(job.key, "applied", notes="Applied on company website")

    apps = db.list_applications()
    assert apps[0]["status"] == "applied"
    assert apps[0]["applied_at"]
    assert apps[0]["notes"] == "Applied on company website"

    # Once actually submitted, later decision changes must not delete application history.
    db.set_job_decision(job.key, "skip")
    apps = db.list_applications()
    assert len(apps) == 1
    assert apps[0]["status"] == "applied"

    db.save_application(job.key, "interview")
    assert db.application_stats()["interview"] == 1
    db.save_application(job.key, "offer")
    assert db.application_stats()["offer"] == 1


def test_rescan_preserves_review_decision(tmp_path, monkeypatch):
    job = setup_db(tmp_path, monkeypatch)
    db.set_job_decision(job.key, "skip")

    rescanned = Job(
        source="Test",
        external_id="abc123",
        title="Werkstudent Supply Chain - Updated",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/job",
        score=92,
    )
    assert db.upsert_job(rescanned) is False
    skipped = db.list_jobs(decision="skip")
    assert len(skipped) == 1
    assert skipped[0]["decision"] == "skip"
    assert skipped[0]["score"] == 92


def test_v2_database_is_migrated_in_place(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "v2.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE jobs (
        job_key TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT NOT NULL, company TEXT, location TEXT, url TEXT, description TEXT,
        created_at TEXT, remote INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0,
        reasons_json TEXT NOT NULL DEFAULT '[]', first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO jobs(job_key,source,external_id,title,first_seen,last_seen)
    VALUES('Legacy:1','Legacy','1','Old job','2026-01-01','2026-01-01');
    """)
    con.commit()
    con.close()

    monkeypatch.setattr(db.settings, "database_path", str(path))
    db.init_db()

    jobs = db.list_jobs(decision="unreviewed")
    assert len(jobs) == 1
    assert jobs[0]["job_key"] == "Legacy:1"
    assert jobs[0]["decision"] == "unreviewed"
    assert db.list_applications() == []
