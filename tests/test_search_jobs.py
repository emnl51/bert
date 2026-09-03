from app import db
from app.profile_store import ensure_profile_schema, list_profiles
from app.search_job_store import (
    create_search_job_run,
    ensure_search_job_schema,
    finish_search_job_run,
    list_search_job_runs,
    list_search_jobs,
    mark_search_job_seen,
    save_search_job,
)
from app.models import Job
from app.search_job_service import keyword_rules_for_job, search_terms_for_job


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


def test_search_terms_are_isolated_and_normalized_per_search_job(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    p = list_profiles()[0]
    job_id = save_search_job(
        {
            "name": "Part-time only",
            "profile_id": p["id"],
            "search_terms": [
                "  Teilzeit Process Engineer  ",
                "part time quality engineer",
                "teilzeit process engineer",
            ],
        }
    )
    saved = next(job for job in list_search_jobs() if job["id"] == job_id)
    assert saved["search_terms"] == ["teilzeit process engineer", "part time quality engineer"]
    planned = search_terms_for_job(saved, p)
    assert planned[:2] == ["process engineer", "quality engineer"]
    assert all(term in planned for term in saved["search_terms"])
    assert not any("werkstudent" in term for term in search_terms_for_job(saved, p))


def test_empty_search_terms_inherit_selected_profile(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    p = list_profiles()[0]
    assert search_terms_for_job({"search_terms": []}, p) == search_terms_for_job({}, p)
    assert "werkstudent supply chain" in search_terms_for_job({}, p)


def test_job_filter_overrides_are_nullable_normalized_and_isolated(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    inherited_id = save_search_job({"name": "Inherited filters", "profile_id": profile["id"]})
    custom_id = save_search_job(
        {
            "name": "Custom filters",
            "profile_id": profile["id"],
            "inherit_location": True,
            "allowlist_terms": [" Automotive ", "automotive", "IATF 16949"],
            "blocklist_terms": [" Software Developer ", "software developer"],
            "allowlist_boost": 18,
        }
    )
    jobs = {job["id"]: job for job in list_search_jobs()}
    assert jobs[inherited_id]["allowlist_terms"] is None
    assert jobs[inherited_id]["blocklist_terms"] is None
    assert jobs[custom_id]["inherit_location"] is True
    assert jobs[custom_id]["allowlist_terms"] == ["automotive", "iatf 16949"]
    assert jobs[custom_id]["blocklist_terms"] == ["software developer"]
    assert jobs[custom_id]["allowlist_boost"] == 18
    assert jobs[custom_id]["min_cv_match"] == 58


def test_cv_match_threshold_is_saved_per_search_job(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    search_id = save_search_job({"name": "Evidence gated", "profile_id": profile["id"], "min_cv_match": 72})
    saved = next(job for job in list_search_jobs() if job["id"] == search_id)
    assert saved["min_cv_match"] == 72


def test_working_time_can_be_preferred_or_strict_per_search_job(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    preferred_id = save_search_job({"name": "Broad discovery", "profile_id": profile["id"]})
    strict_id = save_search_job({"name": "Part-time only", "profile_id": profile["id"], "employment_mode": "strict"})
    jobs = {job["id"]: job for job in list_search_jobs()}
    assert jobs[preferred_id]["employment_mode"] == "prefer"
    assert jobs[strict_id]["employment_mode"] == "strict"


def test_run_history_preserves_filter_reason_counts(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    search_id = save_search_job({"name": "Measured search", "profile_id": profile["id"]})
    run_id = create_search_job_run(search_id)
    counts = {"blocklist": 2, "employment": 1, "fit": 4, "language": 3, "cv_match": 5}
    finish_search_job_run(run_id, search_id, "success", fetched=20, matches=5, filter_counts=counts)
    run = list_search_job_runs(search_id)[0]
    assert run["filter_counts"] == counts


def test_job_filter_rules_inherit_or_replace_profile_values():
    profile = {"keywords": {"allowlist": {"automotive": 12}, "blocklist": {"developer": -100}}}
    inherited = keyword_rules_for_job({}, profile)
    assert inherited["allowlist"] == {"automotive": 12}
    assert inherited["blocklist"] == {"developer": -100}

    custom = keyword_rules_for_job(
        {"allowlist_terms": ["quality engineer"], "blocklist_terms": [], "allowlist_boost": 20},
        profile,
    )
    assert custom["allowlist"] == {"quality engineer": 20}
    assert custom["blocklist"] == {}
