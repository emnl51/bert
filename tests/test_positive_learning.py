from app import db
from app.models import Job
from app.language_store import ensure_language_schema, upsert_language_fit
from app.positive_learning import (
    ensure_positive_schema,
    record_positive_event,
    list_positive_rules,
    apply_positive_boost,
    sync_application_events,
)


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_language_schema()
    ensure_positive_schema()


def add_job():
    job = Job(
        source="test",
        external_id="1",
        title="Working Student Supply Chain Procurement",
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/job",
        description="International supply chain procurement role using SAP, Excel and supplier management.",
    )
    job.score = 55
    job.language_score = 90
    job.language_label = "english_first"
    job.overall_score = 67
    db.upsert_job(job)
    upsert_language_fit(job)
    return job


def test_suitable_event_is_idempotent_and_boosts_similar_jobs(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    first = record_positive_event(job.key, "suitable")
    second = record_positive_event(job.key, "suitable")
    assert first["created"] is True
    assert second["created"] is False
    rules = list_positive_rules()
    assert rules
    candidate = Job(
        source="test",
        external_id="2",
        title="Working Student Supply Chain",
        company="Other GmbH",
        location="Berlin",
        url="https://example.com/2",
        description="Supply chain role with SAP and Excel.",
    )
    candidate.language_label = "english_first"
    boosted, reasons = apply_positive_boost(candidate, 50)
    assert boosted > 50
    assert any("preferred:" in r for r in reasons)


def test_application_status_sync_is_cumulative(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = add_job()
    db.save_application(job.key, "offer")
    created = sync_application_events()
    assert created == 3
    created_again = sync_application_events()
    assert created_again == 0
    with db.connection() as con:
        events = {
            r["event_type"]
            for r in con.execute("SELECT event_type FROM positive_events WHERE job_key=?", (job.key,)).fetchall()
        }
    assert events == {"applied", "interview", "offer"}
    rules = list_positive_rules()
    assert any(r["strongest_event"] == "offer" for r in rules)
