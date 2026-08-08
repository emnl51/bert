import json, re
from datetime import datetime, timezone
from typing import Any
import httpx
from .db import connection, get_setting
from .candidate_store import get_candidate

SCHEMA='''
CREATE TABLE IF NOT EXISTS job_intelligence (
 job_key TEXT NOT NULL,
 candidate_profile_id INTEGER NOT NULL,
 search_job_id INTEGER,
 cv_match INTEGER NOT NULL DEFAULT 0,
 recommendation TEXT NOT NULL DEFAULT 'maybe',
 strengths_json TEXT NOT NULL DEFAULT '[]',
 gaps_json TEXT NOT NULL DEFAULT '[]',
 risks_json TEXT NOT NULL DEFAULT '[]',
 matched_terms_json TEXT NOT NULL DEFAULT '[]',
 missing_terms_json TEXT NOT NULL DEFAULT '[]',
 summary TEXT NOT NULL DEFAULT '',
 engine TEXT NOT NULL DEFAULT 'heuristic-v1',
 analyzed_at TEXT NOT NULL,
 PRIMARY KEY(job_key,candidate_profile_id),
 FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE,
 FOREIGN KEY(candidate_profile_id) REFERENCES candidate_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_job_intelligence_match ON job_intelligence(candidate_profile_id,cv_match DESC);
'''

STOP={'the','and','with','for','from','your','you','our','are','will','this','that','und','der','die','das','mit','für','von','eine','einer','einem','ein','im','in','auf','zu','als','bei','working','student','werkstudent','manager','senior','junior'}
IMPORTANT=('supply chain','procurement','purchasing','sourcing','supply planning','demand planning','material planning','order management','production planning','logistics','operations','supplier management','sap','s/4hana','power bi','excel','erp','inventory','incoterms','rfq','customer management','international business','stakeholder management','leadership','manufacturing','capacity planning','quality','export','amazon')

def _now(): return datetime.now(timezone.utc).isoformat()
def ensure_intelligence_schema():
    with connection() as con: con.executescript(SCHEMA)
def _norm(x): return re.sub(r'\s+',' ',re.sub(r'[^a-zA-ZäöüÄÖÜß0-9+#./ -]+',' ',x or '').lower()).strip()
def _tokens(text): return {w for w in _norm(text).split() if len(w)>=4 and w not in STOP}
def _job(job_key):
    with connection() as con: row=con.execute('SELECT * FROM jobs WHERE job_key=?',(job_key,)).fetchone()
    return dict(row) if row else None

def _heuristic(c,j):
    job_text=_norm(f"{j.get('title','')} {j.get('description','')}")
    cv_text=_norm(f"{c.get('headline','')} {c.get('cv_text','')} {' '.join(c.get('skills',[]))} {' '.join(c.get('target_roles',[]))}")
    matched=[]; missing=[]
    for term in IMPORTANT:
        if term in job_text: (matched if term in cv_text else missing).append(term)
    jt=_tokens(job_text); ct=_tokens(cv_text); overlap=jt & ct
    lexical=min(45, round((len(overlap)/max(1,min(len(jt),80)))*100))
    critical_total=max(1,len(matched)+len(missing)); critical=round(55*len(matched)/critical_total) if matched or missing else 28
    score=max(0,min(100,lexical+critical))
    strengths=[f"Matched: {x}" for x in matched[:6]]
    if len(overlap)>=8: strengths.append('Strong vocabulary overlap with the CV')
    gaps=[f"Not evident in CV: {x}" for x in missing[:6]]
    risks=[]
    if any(x in job_text for x in ('c1 german','c2 german','fluent german','business fluent german','verhandlungssicheres deutsch','deutsch c1')): risks.append('German requirement may exceed the current profile')
    if any(x in job_text for x in ('full-time','full time','vollzeit')) and any('werkstudent' in _norm(x) or 'working student' in _norm(x) for x in c.get('target_roles',[])): risks.append('Employment format may not match the current target')
    rec='apply' if score>=78 else 'maybe' if score>=58 else 'skip'
    return {'cv_match':score,'recommendation':rec,'strengths':strengths,'gaps':gaps,'risks':risks,'matched_terms':matched,'missing_terms':missing,'summary':f"{score}/100 CV match. {len(matched)} important requirements are evident; {len(missing)} are not clearly evidenced in the CV.",'engine':'heuristic-v1'}

def _ollama(c,j,baseline):
    if get_setting('intelligence_ollama_enabled','false').lower() not in ('1','true','yes','on'): return None
    url=get_setting('intelligence_ollama_url','http://host.docker.internal:11434').rstrip('/')
    model=get_setting('intelligence_ollama_model','gemma3')
    prompt=f'''Return JSON only with keys cv_match (0-100 integer), recommendation (apply|maybe|skip), strengths (array), gaps (array), risks (array), summary (short string). Evaluate evidence strictly from the CV. Do not invent experience.\n\nCANDIDATE CV:\n{c.get('cv_text','')[:18000]}\n\nCANDIDATE SKILLS:\n{', '.join(c.get('skills',[]))}\nLANGUAGES: {json.dumps(c.get('languages',{}))}\nTARGET ROLES: {', '.join(c.get('target_roles',[]))}\n\nJOB TITLE: {j.get('title','')}\nJOB DESCRIPTION:\n{j.get('description','')[:18000]}\n\nHeuristic baseline score: {baseline['cv_match']}.''' 
    try:
        with httpx.Client(timeout=90) as client:
            r=client.post(url+'/api/generate',json={'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0.1}}); r.raise_for_status(); payload=r.json(); data=json.loads(payload.get('response','{}'))
        score=max(0,min(100,int(data.get('cv_match',baseline['cv_match'])))); rec=str(data.get('recommendation','maybe')).lower(); rec=rec if rec in ('apply','maybe','skip') else 'maybe'
        return {'cv_match':score,'recommendation':rec,'strengths':list(data.get('strengths') or [])[:8],'gaps':list(data.get('gaps') or [])[:8],'risks':list(data.get('risks') or [])[:8],'matched_terms':baseline['matched_terms'],'missing_terms':baseline['missing_terms'],'summary':str(data.get('summary') or baseline['summary'])[:1000],'engine':f'ollama:{model}'}
    except Exception: return None

def analyze_job(job_key:str,candidate_profile_id:int,search_job_id:int|None=None)->dict[str,Any]:
    ensure_intelligence_schema(); c=get_candidate(candidate_profile_id); j=_job(job_key)
    if not c or not j: raise ValueError('Candidate profile or job not found')
    baseline=_heuristic(c,j); result=_ollama(c,j,baseline) or baseline
    with connection() as con:
        con.execute('''INSERT INTO job_intelligence(job_key,candidate_profile_id,search_job_id,cv_match,recommendation,strengths_json,gaps_json,risks_json,matched_terms_json,missing_terms_json,summary,engine,analyzed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_key,candidate_profile_id) DO UPDATE SET search_job_id=excluded.search_job_id,cv_match=excluded.cv_match,recommendation=excluded.recommendation,strengths_json=excluded.strengths_json,gaps_json=excluded.gaps_json,risks_json=excluded.risks_json,matched_terms_json=excluded.matched_terms_json,missing_terms_json=excluded.missing_terms_json,summary=excluded.summary,engine=excluded.engine,analyzed_at=excluded.analyzed_at''',(job_key,candidate_profile_id,search_job_id,result['cv_match'],result['recommendation'],json.dumps(result['strengths']),json.dumps(result['gaps']),json.dumps(result['risks']),json.dumps(result['matched_terms']),json.dumps(result['missing_terms']),result['summary'],result['engine'],_now()))
    return {'job_key':job_key,'candidate_profile_id':candidate_profile_id,**result}

def get_analysis(job_key:str,candidate_profile_id:int):
    ensure_intelligence_schema()
    with connection() as con: row=con.execute('SELECT * FROM job_intelligence WHERE job_key=? AND candidate_profile_id=?',(job_key,candidate_profile_id)).fetchone()
    if not row: return None
    d=dict(row)
    for k in ('strengths','gaps','risks','matched_terms','missing_terms'): d[k]=json.loads(d.pop(k+'_json') or '[]')
    return d

def list_analyses(candidate_profile_id:int|None=None,limit:int=300):
    ensure_intelligence_schema(); params=[]; where=''
    if candidate_profile_id: where='WHERE i.candidate_profile_id=?'; params.append(candidate_profile_id)
    params.append(limit)
    with connection() as con: rows=con.execute(f'''SELECT i.*,j.title,j.company,j.location,j.url FROM job_intelligence i JOIN jobs j ON j.job_key=i.job_key {where} ORDER BY i.cv_match DESC,i.analyzed_at DESC LIMIT ?''',params).fetchall()
    out=[]
    for row in rows:
        d=dict(row)
        for k in ('strengths','gaps','risks','matched_terms','missing_terms'): d[k]=json.loads(d.pop(k+'_json') or '[]')
        out.append(d)
    return out
