import json
import re
from datetime import datetime, timezone
from typing import Any
from .db import connection

FEEDBACK_SCHEMA='''
CREATE TABLE IF NOT EXISTS job_feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT NOT NULL, profile_id INTEGER NOT NULL DEFAULT 1,
 suitability TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 generated_rules_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
 FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS learned_rules (
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL DEFAULT 1, scope TEXT NOT NULL, term TEXT NOT NULL,
 weight INTEGER NOT NULL DEFAULT -8, evidence_count INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 1,
 source_reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_job ON job_feedback(job_key);
CREATE INDEX IF NOT EXISTS idx_feedback_profile ON job_feedback(profile_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learned_rules_profile ON learned_rules(profile_id,enabled);
'''
STOPWORDS={'werkstudent','working','student','studentin','studentische','m','w','d','f','x','and','und','the','for','für','im','in','of','at','bei','part','time','teilzeit','intern','internship','praktikum','praktikant','praktikantin','junior','senior'}

def _now(): return datetime.now(timezone.utc).isoformat()
def _normalise(text): return re.sub(r'\s+',' ',re.sub(r'[^a-zA-ZäöüÄÖÜß0-9+#./ -]+',' ',text or '').lower()).strip()

def ensure_feedback_schema():
    with connection() as con:
        con.executescript(FEEDBACK_SCHEMA)
        cols={r[1] for r in con.execute('PRAGMA table_info(job_feedback)').fetchall()}
        if 'profile_id' not in cols: con.execute('ALTER TABLE job_feedback ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1')
        cols={r[1] for r in con.execute('PRAGMA table_info(learned_rules)').fetchall()}
        if 'profile_id' not in cols: con.execute('ALTER TABLE learned_rules ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1')
        ddl=con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='learned_rules'").fetchone()
        if ddl and 'UNIQUE(scope, term)' in (ddl['sql'] or ''):
            con.execute('ALTER TABLE learned_rules RENAME TO learned_rules_old_v9')
            con.execute('''CREATE TABLE learned_rules (id INTEGER PRIMARY KEY AUTOINCREMENT,profile_id INTEGER NOT NULL DEFAULT 1,scope TEXT NOT NULL,term TEXT NOT NULL,weight INTEGER NOT NULL DEFAULT -8,evidence_count INTEGER NOT NULL DEFAULT 1,enabled INTEGER NOT NULL DEFAULT 1,source_reason TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(profile_id,scope,term))''')
            con.execute('''INSERT INTO learned_rules(id,profile_id,scope,term,weight,evidence_count,enabled,source_reason,created_at,updated_at) SELECT id,COALESCE(profile_id,1),scope,term,weight,evidence_count,enabled,source_reason,created_at,updated_at FROM learned_rules_old_v9''')
            con.execute('DROP TABLE learned_rules_old_v9')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_learned_profile_scope_term ON learned_rules(profile_id,scope,term)')
    from .positive_learning import ensure_positive_schema
    ensure_positive_schema()

def _role_terms(title):
    words=[w for w in _normalise(title).split() if len(w)>=3 and w not in STOPWORDS]; out=[]
    if len(words)>=2: out.append(' '.join(words[:2]))
    if words: out.append(words[0])
    return list(dict.fromkeys(t for t in out if len(t)>=4))[:2]

def _suggest_rules(job,reason):
    reason=(reason or '').lower(); rules=[]
    if reason=='wrong_role': rules += [{'scope':'title','term':t,'weight':-8} for t in _role_terms(job.get('title',''))]
    elif reason=='company' and _normalise(job.get('company','')): rules=[{'scope':'company','term':_normalise(job.get('company','')),'weight':-10}]
    elif reason=='location' and _normalise(job.get('location','')): rules=[{'scope':'location','term':_normalise(job.get('location','')),'weight':-6}]
    elif reason=='seniority':
        title=_normalise(job.get('title',''))
        rules=[{'scope':'title','term':t,'weight':-7} for t in ('senior','lead','head','director','manager','junior','intern','praktikum') if t in title]
    elif reason=='employment_type':
        text=_normalise(f"{job.get('title','')} {job.get('description','')}")
        rules=[{'scope':'description','term':t,'weight':-7} for t in ('full-time','full time','vollzeit','internship','praktikum','minijob') if t in text]
    elif reason=='german_level': rules=[{'scope':'language','term':'german_heavy','weight':-12}]
    return rules[:3]

def _upsert_rule(con,profile_id,rule,reason):
    row=con.execute('SELECT id,evidence_count,weight FROM learned_rules WHERE profile_id=? AND scope=? AND term=?',(profile_id,rule['scope'],rule['term'])).fetchone(); now=_now()
    if row:
        ev=int(row['evidence_count'])+1; weight=max(-30,min(int(row['weight']),int(rule['weight']))-(1 if ev in (2,4,7) else 0))
        con.execute('UPDATE learned_rules SET evidence_count=?,weight=?,enabled=1,source_reason=?,updated_at=? WHERE id=?',(ev,weight,reason,now,row['id'])); return int(row['id'])
    cur=con.execute('INSERT INTO learned_rules(profile_id,scope,term,weight,evidence_count,enabled,source_reason,created_at,updated_at) VALUES(?,?,?,?,1,1,?,?,?)',(profile_id,rule['scope'],rule['term'],int(rule['weight']),reason,now,now)); return int(cur.lastrowid)

def record_feedback(job_key,suitability,reason='',note='',learn=True,profile_id=1):
    if suitability not in ('suitable','maybe','not_suitable'): raise ValueError('Invalid suitability')
    ensure_feedback_schema()
    with connection() as con:
        row=con.execute('SELECT * FROM jobs WHERE job_key=?',(job_key,)).fetchone()
        if not row: raise ValueError('Job not found')
        rules=_suggest_rules(dict(row),reason) if suitability=='not_suitable' and learn else []
        ids=[_upsert_rule(con,profile_id,r,reason) for r in rules]; now=_now()
        con.execute('INSERT INTO job_feedback(job_key,profile_id,suitability,reason,note,generated_rules_json,created_at) VALUES(?,?,?,?,?,?,?)',(job_key,profile_id,suitability,reason,note or '',json.dumps(ids),now))
        legacy={'suitable':'apply','maybe':'maybe','not_suitable':'skip'}[suitability]
        con.execute('UPDATE jobs SET decision=?,decision_at=? WHERE job_key=?',(legacy,now,job_key))
        if suitability=='suitable':
            con.execute("INSERT INTO applications(job_key,status,created_at,updated_at) VALUES(?,'to_apply',?,?) ON CONFLICT(job_key) DO UPDATE SET updated_at=excluded.updated_at",(job_key,now,now))
    positive_ids=[]
    if suitability=='suitable' and learn:
        from .positive_learning import record_positive_event
        positive_ids=record_positive_event(job_key,'suitable',profile_id=profile_id)['positive_rule_ids']
    return {'job_key':job_key,'profile_id':profile_id,'suitability':suitability,'reason':reason,'learned_rule_ids':ids,'positive_rule_ids':positive_ids}

def list_feedback(limit=100,profile_id=None):
    ensure_feedback_schema(); where=''; params=[]
    if profile_id: where='WHERE f.profile_id=?'; params.append(profile_id)
    params.append(limit)
    with connection() as con: rows=con.execute(f'''SELECT f.*,j.title,j.company,j.location FROM job_feedback f JOIN jobs j ON j.job_key=f.job_key {where} ORDER BY f.id DESC LIMIT ?''',params).fetchall()
    return [dict(r) for r in rows]

def list_learned_rules(profile_id=None):
    ensure_feedback_schema(); where=''; params=[]
    if profile_id: where='WHERE profile_id=?'; params=[profile_id]
    with connection() as con: rows=con.execute(f'SELECT * FROM learned_rules {where} ORDER BY enabled DESC,evidence_count DESC,ABS(weight) DESC,term',params).fetchall()
    negative=[{**dict(r),'enabled':bool(r['enabled']),'polarity':'penalty','strongest_event':''} for r in rows]
    from .positive_learning import list_positive_rules
    positive=[]
    for row in list_positive_rules(profile_id=profile_id):
        item=dict(row); item['id']=-int(item['id']); item['polarity']='boost'; item['source_reason']=item.get('strongest_event',''); positive.append(item)
    return sorted(positive+negative,key=lambda r:(not r['enabled'],-r['evidence_count'],-abs(r['weight']),r['term']))

def set_rule_enabled(rule_id,enabled):
    if rule_id<0:
        from .positive_learning import set_positive_rule_enabled; set_positive_rule_enabled(abs(rule_id),enabled); return
    with connection() as con: con.execute('UPDATE learned_rules SET enabled=?,updated_at=? WHERE id=?',(int(enabled),_now(),rule_id))
def delete_rule(rule_id):
    if rule_id<0:
        from .positive_learning import delete_positive_rule; delete_positive_rule(abs(rule_id)); return
    with connection() as con: con.execute('DELETE FROM learned_rules WHERE id=?',(rule_id,))

def apply_learned_penalty(job,base_score,profile_id=1):
    ensure_feedback_schema()
    with connection() as con: rules=con.execute('SELECT scope,term,weight FROM learned_rules WHERE enabled=1 AND profile_id=?',(profile_id,)).fetchall()
    fields={'title':_normalise(getattr(job,'title','')),'company':_normalise(getattr(job,'company','')),'location':_normalise(getattr(job,'location','')),'description':_normalise(f"{getattr(job,'title','')} {getattr(job,'description','')}"),'language':getattr(job,'language_label','') or ''}
    score=int(base_score); reasons=[]
    for r in rules:
        if r['term'] and r['term'] in fields.get(r['scope'],''): score+=int(r['weight']); reasons.append(f"learned penalty: {r['scope']} '{r['term']}' {r['weight']}")
    return max(0,score),reasons

def feedback_stats(profile_id=None):
    ensure_feedback_schema(); params=[]; pf=''
    if profile_id: pf=' WHERE profile_id=?'; params=[profile_id]
    with connection() as con:
        total=con.execute('SELECT COUNT(*) FROM job_feedback'+pf,params).fetchone()[0]
        bad=con.execute('SELECT COUNT(*) FROM job_feedback'+(pf+' AND ' if pf else ' WHERE ')+"suitability='not_suitable'",params).fetchone()[0]
        rules=con.execute('SELECT COUNT(*) FROM learned_rules'+(pf+' AND ' if pf else ' WHERE ')+'enabled=1',params).fetchone()[0]
    from .positive_learning import positive_stats
    p=positive_stats(profile_id=profile_id)
    return {'feedback_total':total,'not_suitable':bad,'active_rules':rules+p['positive_rules'],'negative_rules':rules,**p}
