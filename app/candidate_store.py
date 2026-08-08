import json
from datetime import datetime, timezone
from typing import Any
from .db import connection
from .secrets import encrypt_secret, decrypt_secret

SCHEMA = '''
CREATE TABLE IF NOT EXISTS candidate_profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL UNIQUE,
 headline TEXT NOT NULL DEFAULT '',
 cv_text TEXT NOT NULL DEFAULT '',
 skills_json TEXT NOT NULL DEFAULT '[]',
 languages_json TEXT NOT NULL DEFAULT '{}',
 target_roles_json TEXT NOT NULL DEFAULT '[]',
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS search_job_candidates (
 search_job_id INTEGER PRIMARY KEY,
 candidate_profile_id INTEGER NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE,
 FOREIGN KEY(candidate_profile_id) REFERENCES candidate_profiles(id) ON DELETE RESTRICT
);
'''

def _now(): return datetime.now(timezone.utc).isoformat()

def ensure_candidate_schema():
    with connection() as con: con.executescript(SCHEMA)

def _decrypt_cv(value:str)->str:
    if not value: return ''
    try: return decrypt_secret(value)
    except Exception: return value

def _decode(row):
    d=dict(row); d['cv_text']=_decrypt_cv(d.get('cv_text','')); d['skills']=json.loads(d.pop('skills_json') or '[]'); d['languages']=json.loads(d.pop('languages_json') or '{}'); d['target_roles']=json.loads(d.pop('target_roles_json') or '[]'); return d

def list_candidates():
    ensure_candidate_schema()
    with connection() as con: rows=con.execute('SELECT * FROM candidate_profiles ORDER BY name').fetchall()
    return [_decode(r) for r in rows]

def get_candidate(candidate_id:int):
    ensure_candidate_schema()
    with connection() as con: row=con.execute('SELECT * FROM candidate_profiles WHERE id=?',(candidate_id,)).fetchone()
    return _decode(row) if row else None

def save_candidate(data:dict[str,Any], candidate_id:int|None=None):
    ensure_candidate_schema(); now=_now(); vals={'name':data.get('name','Candidate').strip(),'headline':data.get('headline','').strip(),'cv_text':encrypt_secret(data.get('cv_text','')) if data.get('cv_text','') else '','skills_json':json.dumps(data.get('skills',[]),ensure_ascii=False),'languages_json':json.dumps(data.get('languages',{}),ensure_ascii=False),'target_roles_json':json.dumps(data.get('target_roles',[]),ensure_ascii=False),'notes':data.get('notes',''),'updated_at':now}
    with connection() as con:
        if candidate_id:
            con.execute('UPDATE candidate_profiles SET name=:name,headline=:headline,cv_text=:cv_text,skills_json=:skills_json,languages_json=:languages_json,target_roles_json=:target_roles_json,notes=:notes,updated_at=:updated_at WHERE id=:id',{**vals,'id':candidate_id}); return candidate_id
        cur=con.execute('INSERT INTO candidate_profiles(name,headline,cv_text,skills_json,languages_json,target_roles_json,notes,created_at,updated_at) VALUES(:name,:headline,:cv_text,:skills_json,:languages_json,:target_roles_json,:notes,:created_at,:updated_at)',{**vals,'created_at':now}); return int(cur.lastrowid)

def delete_candidate(candidate_id:int):
    ensure_candidate_schema()
    with connection() as con:
        used=con.execute('SELECT COUNT(*) FROM search_job_candidates WHERE candidate_profile_id=?',(candidate_id,)).fetchone()[0]
        if used: raise ValueError('Candidate profile is assigned to a Search Job')
        con.execute('DELETE FROM candidate_profiles WHERE id=?',(candidate_id,))

def assign_candidate(search_job_id:int,candidate_profile_id:int|None,enabled:bool=True):
    ensure_candidate_schema()
    with connection() as con:
        if not candidate_profile_id: con.execute('DELETE FROM search_job_candidates WHERE search_job_id=?',(search_job_id,)); return
        con.execute('INSERT INTO search_job_candidates(search_job_id,candidate_profile_id,enabled) VALUES(?,?,?) ON CONFLICT(search_job_id) DO UPDATE SET candidate_profile_id=excluded.candidate_profile_id,enabled=excluded.enabled',(search_job_id,candidate_profile_id,int(enabled)))

def candidate_for_search_job(search_job_id:int):
    ensure_candidate_schema()
    with connection() as con:
        row=con.execute('''SELECT c.* FROM search_job_candidates m JOIN candidate_profiles c ON c.id=m.candidate_profile_id WHERE m.search_job_id=? AND m.enabled=1''',(search_job_id,)).fetchone()
    return _decode(row) if row else None

def mapping_for_jobs():
    ensure_candidate_schema()
    with connection() as con: rows=con.execute('SELECT search_job_id,candidate_profile_id,enabled FROM search_job_candidates').fetchall()
    return [dict(r) for r in rows]
