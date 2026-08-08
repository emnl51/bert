from app import db
from app.source_analytics import ensure_source_analytics_schema, save_source_run_stats, source_quality_summary


def test_source_quality_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, 'database_path', str(tmp_path / 'jobs.db'))
    db.init_db()
    ensure_source_analytics_schema()
    save_source_run_stats(1, {
        'JobSpy / linkedin': {
            'fetched': 100,
            'unique_jobs': 90,
            'job_fit': 40,
            'language_fit': 35,
            'recommended': 20,
            'new_matches': 10,
        }
    })
    row = source_quality_summary(20)[0]
    assert row['source'] == 'JobSpy / linkedin'
    assert row['quality_pct'] == 20.0
    assert row['new_yield_pct'] == 10.0
    assert row['dedupe_pct'] == 10.0
