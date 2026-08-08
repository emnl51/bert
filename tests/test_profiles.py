from app import db
from app.models import Job
from app.profile_store import ensure_profile_schema, list_profiles, upsert_profile_score, list_jobs_for_profile
from app.feedback_store import ensure_feedback_schema, record_feedback, apply_learned_penalty
from app.positive_learning import record_positive_event, apply_positive_boost


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, 'database_path', str(tmp_path / 'jobs.db'))
    db.init_db()
    ensure_profile_schema()
    ensure_feedback_schema()


def add_job():
    job = Job(source='test', external_id='multi-1', title='Working Student Supply Chain Procurement',
              company='Example GmbH', location='Berlin', url='https://example.com/multi-1',
              description='Supply chain procurement role using SAP and Excel in an international team.')
    job.score=70; job.language_score=90; job.language_label='english_first'; job.language_reasons=[]; job.overall_score=77; job.reasons=['base']
    db.upsert_job(job)
    return job


def test_default_profiles_are_seeded(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    profiles=list_profiles()
    assert len(profiles) >= 2
    assert profiles[0]['is_default'] is True
    assert any(p['slug']=='werkstudent' for p in profiles)
    assert any(p['slug']=='fulltime' for p in profiles)


def test_same_job_keeps_independent_profile_scores(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job=add_job(); profiles=list_profiles(); a,b=profiles[0],profiles[1]
    upsert_profile_score(job,a['id'])
    job.score=42; job.language_score=60; job.overall_score=47; job.language_label='stretch'; job.reasons=['fulltime score']
    upsert_profile_score(job,b['id'])
    rows_a=list_jobs_for_profile(a['id'],decision='all',language='all')
    rows_b=list_jobs_for_profile(b['id'],decision='all',language='all')
    assert rows_a[0]['overall_score']==77
    assert rows_b[0]['overall_score']==47
    assert rows_a[0]['language_label']=='english_first'
    assert rows_b[0]['language_label']=='stretch'


def test_learning_is_isolated_by_profile(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job=add_job(); profiles=list_profiles(); a,b=profiles[0],profiles[1]
    upsert_profile_score(job,a['id']); upsert_profile_score(job,b['id'])
    record_feedback(job.key,'not_suitable','wrong_role',learn=True,profile_id=a['id'])
    candidate=Job(source='test',external_id='multi-2',title='Working Student Supply Chain Procurement',company='Other',location='Berlin',url='https://example.com/2',description='Supply chain procurement')
    candidate.language_label='english_first'
    penalized,_=apply_learned_penalty(candidate,60,profile_id=a['id'])
    untouched,_=apply_learned_penalty(candidate,60,profile_id=b['id'])
    assert penalized < 60
    assert untouched == 60
    record_positive_event(job.key,'suitable',profile_id=b['id'])
    boosted,_=apply_positive_boost(candidate,60,profile_id=b['id'])
    no_boost,_=apply_positive_boost(candidate,60,profile_id=a['id'])
    assert boosted > 60
    assert no_boost == penalized or no_boost == 60
