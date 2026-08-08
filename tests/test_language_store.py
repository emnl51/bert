from app import db
from app.language_store import ensure_language_schema, enrich_applications, list_jobs_with_language, upsert_language_fit
from app.models import Job


def setup_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, 'database_path', str(tmp_path / 'jobs.db'))
    db.init_db()
    ensure_language_schema()


def test_language_schema_seeds_profile_and_search_terms(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    assert db.get_setting('current_german_level') == 'a2_b1'
    assert db.get_setting('min_language_score') == '40'
    terms = {x['term'] for x in db.list_keywords('search')}
    assert 'working student supply chain english' in terms


def test_language_fit_is_stored_and_filterable(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = Job(
        source='test', external_id='1', title='Working Student Supply Chain', company='Example',
        location='Berlin', url='https://example.com', score=82, language_score=94,
        overall_score=86, language_label='german_growth', language_reasons=['German optional / plus'],
    )
    assert db.upsert_job(job) is True
    upsert_language_fit(job)
    jobs = list_jobs_with_language(language='german_growth', min_language_score=80)
    assert len(jobs) == 1
    assert jobs[0]['overall_score'] == 86
    assert jobs[0]['language_label'] == 'german_growth'


def test_old_jobs_without_language_row_remain_visible(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = Job(source='test', external_id='old', title='Old role', company='Example', location='Berlin', url='https://example.com', score=70)
    db.upsert_job(job)
    jobs = list_jobs_with_language(language='all')
    assert jobs[0]['overall_score'] == 70
    assert jobs[0]['language_score'] == 55
    assert jobs[0]['language_label'] == 'unclear'


def test_application_enrichment_uses_language_fit(tmp_path, monkeypatch):
    setup_db(tmp_path, monkeypatch)
    job = Job(
        source='test', external_id='2', title='Werkstudent Procurement', company='Example',
        location='Berlin', url='https://example.com/2', score=80, language_score=92,
        overall_score=84, language_label='english_first',
    )
    db.upsert_job(job)
    upsert_language_fit(job)
    db.set_job_decision(job.key, 'apply')
    apps = enrich_applications(db.list_applications())
    assert apps[0]['overall_score'] == 84
    assert apps[0]['language_label'] == 'english_first'
