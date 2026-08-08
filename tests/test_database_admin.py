from pathlib import Path

from app import db
from app.database_admin import backup_database, reset_database
from app.feedback_store import ensure_feedback_schema
from app.models import Job
from app.profile_store import ensure_profile_schema
from app.search_job_store import ensure_search_job_schema


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, 'database_path', str(tmp_path / 'jobtrack.db'))
    import app.database_admin as database_admin
    monkeypatch.setattr(database_admin.settings, 'database_path', str(tmp_path / 'jobtrack.db'))
    db.init_db(); ensure_profile_schema(); ensure_search_job_schema(); ensure_feedback_schema()


def test_backup_database_creates_snapshot(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    path = backup_database()
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_operational_reset_preserves_configuration(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    job = Job(source='test', external_id='1', title='Supply Chain Working Student', company='Example', location='Berlin', url='https://example.com/1')
    db.upsert_job(job)
    before_sources = len(db.list_sources())
    result = reset_database('operational', create_backup=True)
    assert result['verified'] is True
    assert result['remaining'] == {}
    assert result['after']['jobs'] == 0
    assert result['rows_deleted'] >= 1
    with db.connection() as con:
        assert con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM sources').fetchone()[0] == before_sources
        assert con.execute('SELECT COUNT(*) FROM search_profiles').fetchone()[0] >= 1


def test_jobs_reset_reports_zero_jobs(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    for i in range(3):
        db.upsert_job(Job(source='test', external_id=str(i), title=f'Job {i}', company='Example', location='Berlin', url=f'https://example.com/{i}'))
    result = reset_database('jobs', create_backup=False)
    assert result['verified'] is True
    assert result['before']['jobs'] == 3
    assert result['after']['jobs'] == 0
    assert result['deleted']['jobs'] == 3


def test_factory_reset_reseeds_defaults(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    with db.connection() as con:
        con.execute("UPDATE sources SET name='Changed Source' WHERE id=(SELECT MIN(id) FROM sources)")
    result = reset_database('factory', create_backup=True)
    assert result['verified'] is True
    assert result['remaining'] == {}
    assert result['after']['jobs'] == 0
    assert result['backup_path']
    with db.connection() as con:
        assert con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM sources').fetchone()[0] >= 1
        assert con.execute('SELECT COUNT(*) FROM search_profiles').fetchone()[0] >= 2
        assert con.execute('SELECT COUNT(*) FROM search_jobs').fetchone()[0] >= 1
