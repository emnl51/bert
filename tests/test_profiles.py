from app import db
from app.models import Job
from app.profile_store import (
    ensure_profile_schema,
    get_job_for_profile,
    list_jobs_for_profile,
    list_profiles,
    upsert_profile_score,
)
from app.feedback_store import ensure_feedback_schema, record_feedback, apply_learned_penalty
from app.positive_learning import record_positive_event, apply_positive_boost


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_profile_schema()
    ensure_feedback_schema()


def add_job():
    job = Job(
        source="test",
        external_id="multi-1",
        title="Working Student Supply Chain Procurement",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/multi-1",
        description="Supply chain procurement role using SAP and Excel in an international team.",
    )
    job.score = 70
    job.language_score = 90
    job.language_label = "english_first"
    job.language_reasons = []
    job.overall_score = 77
    job.reasons = ["base"]
    db.upsert_job(job)
    return job


def test_default_profiles_are_seeded(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profiles = list_profiles()
    assert len(profiles) >= 2
    assert profiles[0]["is_default"] is True
    assert any(p["slug"] == "werkstudent" for p in profiles)
    assert any(p["slug"] == "fulltime" for p in profiles)


def test_same_job_keeps_independent_profile_scores(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    profiles = list_profiles()
    a, b = profiles[0], profiles[1]
    upsert_profile_score(job, a["id"])
    job.score = 42
    job.language_score = 60
    job.overall_score = 47
    job.language_label = "stretch"
    job.reasons = ["fulltime score"]
    upsert_profile_score(job, b["id"])
    rows_a = list_jobs_for_profile(a["id"], decision="all", language="all")
    rows_b = list_jobs_for_profile(b["id"], decision="all", language="all")
    assert rows_a[0]["overall_score"] == 77
    assert rows_b[0]["overall_score"] == 47
    assert rows_a[0]["language_label"] == "english_first"
    assert rows_b[0]["language_label"] == "stretch"
    assert rows_a[0]["primary_category"] == "Procurement"
    assert "employment_label" in rows_a[0]
    assert "freshness_label" in rows_a[0]
    assert "description_preview" in rows_a[0]


def test_job_ad_language_can_be_filtered_independently(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    profile = list_profiles()[0]
    upsert_profile_score(job, profile["id"])

    assert list_jobs_for_profile(profile["id"], decision="all", language="all", content_language="en")
    assert not list_jobs_for_profile(profile["id"], decision="all", language="all", content_language="de")


def test_complete_job_detail_is_limited_to_scored_profile(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    profiles = list_profiles()
    upsert_profile_score(job, profiles[0]["id"])

    detail = get_job_for_profile(job.key, profiles[0]["id"])

    assert detail is not None
    assert detail["description"] == job.description
    assert detail["overall_score"] == 77
    assert get_job_for_profile(job.key, profiles[1]["id"]) is None


def test_role_irrelevant_scores_are_not_shown_in_review_queue(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    relevant = add_job()
    upsert_profile_score(relevant, profile["id"], role_relevant=True, match_tier="strong")
    irrelevant = Job(
        source="test",
        external_id="software-1",
        title="Software Quality Engineer",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/software-1",
        description="Cloud test automation and backend quality.",
    )
    irrelevant.score = 82
    irrelevant.language_score = 92
    irrelevant.overall_score = 86
    db.upsert_job(irrelevant)
    upsert_profile_score(irrelevant, profile["id"], role_relevant=False, match_tier="excluded")
    hard_constraint = Job(
        source="test",
        external_id="strict-full-time",
        title="Supply Chain Manager",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/strict-full-time",
    )
    hard_constraint.score = 82
    hard_constraint.language_score = 92
    hard_constraint.overall_score = 86
    db.upsert_job(hard_constraint)
    upsert_profile_score(hard_constraint, profile["id"], role_relevant=True, match_tier="excluded")

    rows = list_jobs_for_profile(profile["id"], decision="all", language="all")
    assert [row["job_key"] for row in rows] == [relevant.key]
    assert rows[0]["match_tier"] == "strong"
    assert not list_jobs_for_profile(profile["id"], decision="all", language="all", tier="stretch")
    assert get_job_for_profile(hard_constraint.key, profile["id"]) is None


def test_profile_score_migration_hides_soft_signal_only_legacy_rows(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profile = list_profiles()[0]
    relevant = add_job()
    irrelevant = Job(
        source="test",
        external_id="legacy-noise",
        title="Android Engineer",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/legacy-noise",
    )
    db.upsert_job(irrelevant)
    with db.connection() as con:
        con.execute("DROP TABLE job_profile_scores")
        con.execute(
            """CREATE TABLE job_profile_scores (
                job_key TEXT NOT NULL,profile_id INTEGER NOT NULL,job_score INTEGER NOT NULL DEFAULT 0,
                language_score INTEGER NOT NULL DEFAULT 55,overall_score INTEGER NOT NULL DEFAULT 0,
                language_label TEXT NOT NULL DEFAULT 'unclear',reasons_json TEXT NOT NULL DEFAULT '[]',
                language_reasons_json TEXT NOT NULL DEFAULT '[]',updated_at TEXT NOT NULL,
                PRIMARY KEY(job_key,profile_id))"""
        )
        values = (profile["id"], 80, 92, 84, "english_first", "[]", "2026-09-02T00:00:00+00:00")
        con.execute(
            """INSERT INTO job_profile_scores
               (job_key,profile_id,job_score,language_score,overall_score,language_label,reasons_json,
                language_reasons_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (relevant.key, *values[:5], '["title: supply chain"]', *values[5:]),
        )
        con.execute(
            """INSERT INTO job_profile_scores
               (job_key,profile_id,job_score,language_score,overall_score,language_label,reasons_json,
                language_reasons_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (irrelevant.key, *values[:5], '["skill: sap", "target area"]', *values[5:]),
        )

    rows = list_jobs_for_profile(profile["id"], decision="all", language="all")
    assert [row["job_key"] for row in rows] == [relevant.key]
    assert rows[0]["match_tier"] == "strong"


def test_learning_is_isolated_by_profile(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    profiles = list_profiles()
    a, b = profiles[0], profiles[1]
    upsert_profile_score(job, a["id"])
    upsert_profile_score(job, b["id"])
    record_feedback(job.key, "not_suitable", "wrong_role", learn=True, profile_id=a["id"])
    candidate = Job(
        source="test",
        external_id="multi-2",
        title="Working Student Supply Chain Procurement",
        company="Other",
        location="Berlin",
        url="https://example.com/2",
        description="Supply chain procurement",
    )
    candidate.language_label = "english_first"
    penalized, _ = apply_learned_penalty(candidate, 60, profile_id=a["id"])
    untouched, _ = apply_learned_penalty(candidate, 60, profile_id=b["id"])
    assert penalized < 60
    assert untouched == 60
    record_positive_event(job.key, "suitable", profile_id=b["id"])
    boosted, _ = apply_positive_boost(candidate, 60, profile_id=b["id"])
    no_boost, _ = apply_positive_boost(candidate, 60, profile_id=a["id"])
    assert boosted > 60
    assert no_boost == penalized or no_boost == 60
