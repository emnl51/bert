import json

from app import db
from app import intelligence as intel
from app.models import Job
from app.candidate_store import ensure_candidate_schema, save_candidate, get_candidate
from app.intelligence import ensure_intelligence_schema, analyze_job, get_analysis


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings,'database_path',str(tmp_path/'jobs.db'))
    db.init_db(); ensure_candidate_schema(); ensure_intelligence_schema()


def _candidate():
    return {
        'name':'Process Candidate',
        'headline':'Automotive Process and Quality Engineer',
        'cv_text':'12+ years automotive manufacturing experience. Process optimization, PFMEA, SPC, 8D, OEE, supplier quality, ERP and Excel. Engineering degree. Operator training and audit support.',
        'skills':['PFMEA','SPC','8D','OEE','ERP','Excel','Supplier Quality'],
        'languages':{'English':'professional','German':'A2-B1'},
        'target_roles':['Process Engineer','Quality Engineer'],
    }


def _job():
    return Job(
        source='test',external_id='1',title='Process Engineer',company='Example',location='Berlin',url='https://example.com/1',
        description='Automotive manufacturing role requiring minimum 5 years experience, PFMEA, SPC, root cause analysis, SAP, process optimization, operator training and engineering degree.'
    )


def test_candidate_cv_is_round_tripped_and_evidence_analysis_is_created(tmp_path, monkeypatch):
    setup(tmp_path,monkeypatch)
    cid=save_candidate(_candidate())
    candidate=get_candidate(cid)
    assert '12+ years' in candidate['cv_text'].lower()
    job=_job(); db.upsert_job(job)
    result=analyze_job(job.key,cid,1)
    assert result['cv_match'] >= 50
    assert result['deterministic_score'] == result['cv_match']
    assert result['ai_score'] is None
    assert result['engine'] == 'evidence-v2'
    assert result['recommendation'] in ('apply','maybe','skip')
    assert set(result['breakdown']) == {'role','experience','technical','tools','industry','education','responsibilities'}
    assert any(e['term']=='pfmea' and e['status']=='match' for e in result['evidence'])
    assert any(e['term']=='sap' and e['status']=='missing' for e in result['evidence'])
    assert any(e['category']=='experience' and e['status']=='match' for e in result['evidence'])
    stored=get_analysis(job.key,cid)
    assert stored['cv_match']==result['cv_match']
    assert stored['evidence']
    assert stored['requirements']


def test_unchanged_candidate_and_job_use_cached_analysis(tmp_path, monkeypatch):
    setup(tmp_path,monkeypatch)
    cid=save_candidate(_candidate()); job=_job(); db.upsert_job(job)
    first=analyze_job(job.key,cid,1)
    second=analyze_job(job.key,cid,1)
    assert first['cached'] is False
    assert second['cached'] is True
    assert second['cache_key'] == first['cache_key']
    assert second['cv_match'] == first['cv_match']


def test_ollama_is_only_thirty_percent_and_cannot_change_evidence(tmp_path, monkeypatch):
    setup(tmp_path,monkeypatch)
    cid=save_candidate(_candidate()); job=_job(); db.upsert_job(job)

    settings={
        'intelligence_ollama_enabled':'true',
        'intelligence_ollama_url':'http://ollama.test',
        'intelligence_ollama_model':'test-model',
        'intelligence_ollama_timeout_seconds':'30',
    }
    monkeypatch.setattr(intel,'get_setting',lambda key,default='': settings.get(key,default))

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {'response':json.dumps({
                'contextual_score':100,
                'context_notes':[{'evidence_ref':'tools:sap','text':'SAP is a gap; ERP experience is adjacent but not proof of SAP.'}],
                'transferable':[{'evidence_ref':'tools:sap','text':'ERP experience may help onboarding to SAP.'}],
                'summary':'Strong manufacturing context, with SAP still unsupported by direct CV evidence.',
            })}

    class FakeClient:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,*args,**kwargs): return FakeResponse()

    monkeypatch.setattr(intel.httpx,'Client',FakeClient)
    result=analyze_job(job.key,cid,1,force=True)
    expected=round(result['deterministic_score']*0.70+100*0.30)
    assert result['ai_score']==100
    assert result['cv_match']==expected
    assert result['engine']=='hybrid-v2+ollama:test-model'
    assert any(e['term']=='sap' and e['status']=='missing' for e in result['evidence'])
    assert result['ai_context']['context_notes'][0]['evidence_ref']=='tools:sap'


def test_ai_context_rejects_unknown_evidence_references(tmp_path, monkeypatch):
    setup(tmp_path,monkeypatch)
    cid=save_candidate(_candidate()); job=_job(); db.upsert_job(job)
    settings={'intelligence_ollama_enabled':'true','intelligence_ollama_url':'http://ollama.test','intelligence_ollama_model':'test-model'}
    monkeypatch.setattr(intel,'get_setting',lambda key,default='': settings.get(key,default))

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {'response':json.dumps({'contextual_score':95,'context_notes':[{'evidence_ref':'invented:skill','text':'Invented skill'}],'transferable':[],'summary':'Test'})}
    class FakeClient:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,*args,**kwargs): return FakeResponse()
    monkeypatch.setattr(intel.httpx,'Client',FakeClient)
    result=analyze_job(job.key,cid,force=True)
    assert result['ai_context']['context_notes']==[]
