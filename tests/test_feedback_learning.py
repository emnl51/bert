from app import db
from app.feedback_store import apply_learned_penalty, ensure_feedback_schema, list_learned_rules, record_feedback
from app.models import Job


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, 'database_path', str(tmp_path / 'jobs.db'))
    db.init_db()
    ensure_feedback_schema()


def insert_job(job: Job):
    db.upsert_job(job)


def test_not_suitable_creates_learned_rule(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = Job(source='test', external_id='1', title='Software Developer Working Student', company='Example', location='Berlin', url='https://example.com/1')
    insert_job(job)
    result = record_feedback(job.key, 'not_suitable', 'wrong_role', learn=True)
    assert result['learned_rule_ids']
    rules = list_learned_rules()
    assert any(r['scope'] == 'title' and r['enabled'] for r in rules)


def test_learned_rule_reduces_future_score(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    source = Job(source='test', external_id='1', title='Software Developer Working Student', company='Example', location='Berlin', url='https://example.com/1')
    insert_job(source)
    record_feedback(source.key, 'not_suitable', 'wrong_role', learn=True)
    future = Job(source='test', external_id='2', title='Software Developer Werkstudent', company='Other', location='Berlin', url='https://example.com/2')
    score, reasons = apply_learned_penalty(future, 80)
    assert score < 80
    assert any('learned:' in r for r in reasons)


def test_suitable_job_enters_application_tracker(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = Job(source='test', external_id='1', title='Supply Chain Working Student', company='Example', location='Berlin', url='https://example.com/1')
    insert_job(job)
    record_feedback(job.key, 'suitable')
    apps = db.list_applications()
    assert len(apps) == 1
    assert apps[0]['status'] == 'to_apply'
