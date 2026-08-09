from app import db
from app.profile_store import ensure_profile_schema, list_profiles
from app.search_job_store import ensure_search_job_schema, list_search_jobs, save_search_job, mark_search_job_seen
from app.models import Job


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_profile_schema()
    ensure_search_job_schema()


def test_multiple_search_jobs_can_share_profile(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    p = list_profiles()[0]
    one = save_search_job(
        {"name": "Berlin Daily", "profile_id": p["id"], "target_location": "Berlin", "frequency": "daily"}
    )
    two = save_search_job(
        {"name": "Hennigsdorf Weekly", "profile_id": p["id"], "target_location": "Hennigsdorf", "frequency": "weekly"}
    )
    jobs = list_search_jobs()
    ids = {j["id"] for j in jobs}
    assert one in ids and two in ids


def test_seen_state_is_independent_per_search_job(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    p = list_profiles()[0]
    one = save_search_job({"name": "Search A", "profile_id": p["id"]})
    two = save_search_job({"name": "Search B", "profile_id": p["id"]})
    job = Job(
        source="test",
        external_id="1",
        title="Supply Chain Working Student",
        company="Example",
        location="Berlin",
        url="https://example.com/1",
    )
    db.upsert_job(job)
    assert mark_search_job_seen(one, job.key) is True
    assert mark_search_job_seen(one, job.key) is False
    assert mark_search_job_seen(two, job.key) is True


def test_search_job_notification_settings_are_isolated(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    p = list_profiles()[0]
    a = save_search_job(
        {
            "name": "Telegram Search",
            "profile_id": p["id"],
            "notify_telegram": True,
            "notification": {"telegram_chat_id": "123"},
        }
    )
    b = save_search_job(
        {
            "name": "Email Search",
            "profile_id": p["id"],
            "notify_email": True,
            "notification": {"email_to": "user@example.com"},
        }
    )
    jobs = {j["id"]: j for j in list_search_jobs()}
    assert jobs[a]["notify_telegram"] is True and jobs[a]["notify_email"] is False
    assert jobs[b]["notify_email"] is True and jobs[b]["notify_telegram"] is False
