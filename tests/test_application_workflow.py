from app import db
from app.feedback_store import record_feedback
from app.models import Job
from app.profile_store import ensure_profile_schema, save_profile


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
    with db.connection() as con:
        assert con.execute("SELECT COUNT(*) FROM application_events").fetchone()[0] == 0
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


def test_application_next_actions_events_and_funnel(tmp_path, monkeypatch):
    job = setup_db(tmp_path, monkeypatch)
    db.set_job_decision(job.key, "apply")

    saved = db.save_application(
        job.key,
        "applied",
        notes="Applied through the company portal",
        next_action="Send a concise follow-up",
        next_action_at="2020-01-02",
        contact_name="Erika Recruiter",
    )

    assert saved["next_action"] == "Send a concise follow-up"
    application = db.list_applications()[0]
    assert application["contact_name"] == "Erika Recruiter"
    assert application["next_action_at"] == "2020-01-02"
    events = db.list_application_events(job.key)
    assert [event["event_type"] for event in events] == ["status", "created"]
    assert events[0]["from_status"] == "to_apply"
    assert events[0]["to_status"] == "applied"

    funnel = db.application_funnel()
    assert funnel["stages"]["applied"] == 1
    assert funnel["funnel"] == {"tracked": 1, "applied": 1, "interview": 0, "offer": 0}
    assert funnel["due_actions"] == 1
    assert funnel["sources"] == [{"source": "Test", "tracked": 1, "progressed": 0, "offers": 0}]

    db.save_application(job.key, "interview")
    db.save_application(job.key, "rejected")
    progressed = db.application_funnel()
    assert progressed["stages"]["rejected"] == 1
    assert progressed["funnel"]["interview"] == 1
    assert progressed["sources"][0]["progressed"] == 1


def test_application_workspace_columns_are_migrated_in_place(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "application-v18.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE jobs (
        job_key TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        title TEXT NOT NULL, company TEXT, location TEXT, url TEXT, description TEXT,
        created_at TEXT, remote INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0,
        reasons_json TEXT NOT NULL DEFAULT '[]', first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0,
        decision TEXT NOT NULL DEFAULT 'unreviewed', decision_at TEXT,
        content_language TEXT NOT NULL DEFAULT 'unknown', content_language_confidence REAL NOT NULL DEFAULT 0,
        content_language_source TEXT NOT NULL DEFAULT 'detected'
    );
    CREATE TABLE applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner_key TEXT NOT NULL DEFAULT 'admin', user_id INTEGER,
        profile_id INTEGER, job_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'to_apply', applied_at TEXT,
        notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(owner_key,job_key)
    );
    INSERT INTO jobs(job_key,source,external_id,title,first_seen,last_seen)
    VALUES('Legacy:application','Legacy','application','Legacy role','2026-01-01','2026-01-01');
    INSERT INTO applications(owner_key,job_key,status,notes,created_at,updated_at)
    VALUES('admin','Legacy:application','applied','preserve me','2026-01-02','2026-01-02');
    """)
    con.commit()
    con.close()

    monkeypatch.setattr(db.settings, "database_path", str(path))
    db.init_db()

    application = db.list_applications()[0]
    assert application["notes"] == "preserve me"
    assert application["next_action"] == ""
    assert application["next_action_at"] is None
    assert application["contact_name"] == ""
    assert db.list_application_events("Legacy:application") == []


def test_applications_are_scoped_to_the_profile_that_created_them(tmp_path, monkeypatch):
    job = setup_db(tmp_path, monkeypatch)
    ensure_profile_schema()
    planning_profile = save_profile({"name": "Planning", "slug": "planning"})
    quality_profile = save_profile({"name": "Quality", "slug": "quality"})

    record_feedback(job.key, "suitable", profile_id=planning_profile)

    planning_apps = db.list_applications(profile_id=planning_profile)
    assert [app["job_key"] for app in planning_apps] == [job.key]
    assert db.list_applications(profile_id=quality_profile) == []
    assert db.application_stats(profile_id=planning_profile)["to_apply"] == 1
    assert db.application_stats(profile_id=quality_profile)["total"] == 0


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
