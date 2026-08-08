from app import db
from app.models import Job
from app.candidate_store import ensure_candidate_schema, save_candidate, get_candidate
from app.intelligence import ensure_intelligence_schema, analyze_job, get_analysis


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings,'database_path',str(tmp_path/'jobs.db'))
    db.init_db(); ensure_candidate_schema(); ensure_intelligence_schema()


def test_candidate_cv_is_round_tripped_and_analysis_is_created(tmp_path, monkeypatch):
    setup(tmp_path,monkeypatch)
    cid=save_candidate({
        'name':'Supply Candidate','headline':'Supply Chain and International Operations',
        'cv_text':'Experienced in procurement supply chain manufacturing ERP Excel supplier management international business.',
        'skills':['Supply Chain','Procurement','ERP','Excel','Supplier Management'],
        'languages':{'English':'professional','German':'A2-B1'},
        'target_roles':['Supply Chain Manager'],
    })
    candidate=get_candidate(cid)
    assert 'procurement' in candidate['cv_text'].lower()
    job=Job(source='test',external_id='1',title='Supply Chain Manager',company='Example',location='Berlin',url='https://example.com/1',description='Lead procurement, supplier management, ERP, Excel and international supply chain operations.')
    db.upsert_job(job)
    result=analyze_job(job.key,cid,1)
    assert result['cv_match'] >= 50
    assert result['recommendation'] in ('apply','maybe','skip')
    stored=get_analysis(job.key,cid)
    assert stored['cv_match']==result['cv_match']
    assert stored['strengths']
