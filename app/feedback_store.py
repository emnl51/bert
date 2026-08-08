import json
import re
from datetime import datetime, timezone
from typing import Any

from .db import connection

FEEDBACK_SCHEMA = '''
CREATE TABLE IF NOT EXISTS job_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL,
    suitability TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    generated_rules_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_feedback_job ON job_feedback(job_key);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON job_feedback(created_at DESC);

CREATE TABLE IF NOT EXISTS learned_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    term TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT -8,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    source_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(scope, term)
);
CREATE INDEX IF NOT EXISTS idx_learned_rules_enabled ON learned_rules(enabled);
'''

STOPWORDS = {
    'werkstudent','working','student','studentin','studentische','m','w','d','f','x','and','und','the','for','für','im','in','of','at','bei',
    'part','time','teilzeit','intern','internship','praktikum','praktikant','praktikantin','junior','senior'
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_feedback_schema() -> None:
    with connection() as con:
        con.executescript(FEEDBACK_SCHEMA)


def _normalise(text: str) -> str:
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß0-9+#./ -]+', ' ', text or '').lower()
    return re.sub(r'\s+', ' ', text).strip()


def _role_terms(title: str) -> list[str]:
    words = [w for w in _normalise(title).split() if len(w) >= 3 and w not in STOPWORDS]
    terms: list[str] = []
    if len(words) >= 2:
        terms.append(' '.join(words[:2]))
    if words:
        terms.append(words[0])
    return list(dict.fromkeys(t for t in terms if len(t) >= 4))[:2]


def _suggest_rules(job: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    reason = (reason or '').strip().lower()
    rules: list[dict[str, Any]] = []
    if reason == 'wrong_role':
        rules.extend({'scope': 'title', 'term': t, 'weight': -8} for t in _role_terms(job.get('title', '')))
    elif reason == 'company':
        company = _normalise(job.get('company', ''))
        if company:
            rules.append({'scope': 'company', 'term': company, 'weight': -10})
    elif reason == 'location':
        location = _normalise(job.get('location', ''))
        if location:
            rules.append({'scope': 'location', 'term': location, 'weight': -6})
    elif reason == 'seniority':
        title = _normalise(job.get('title', ''))
        for term in ('senior', 'lead', 'head', 'director', 'manager', 'junior', 'intern', 'praktikum'):
            if term in title:
                rules.append({'scope': 'title', 'term': term, 'weight': -7})
    elif reason == 'employment_type':
        text = _normalise(f"{job.get('title','')} {job.get('description','')}")
        for term in ('full-time', 'full time', 'vollzeit', 'internship', 'praktikum', 'minijob'):
            if term in text:
                rules.append({'scope': 'description', 'term': term, 'weight': -7})
    elif reason == 'german_level':
        rules.append({'scope': 'language', 'term': 'german_heavy', 'weight': -12})
    return rules[:3]


def _upsert_rule(con, rule: dict[str, Any], reason: str) -> int:
    now = _now()
    row = con.execute('SELECT id,evidence_count,weight FROM learned_rules WHERE scope=? AND term=?', (rule['scope'], rule['term'])).fetchone()
    if row:
        evidence = int(row['evidence_count']) + 1
        weight = max(-30, min(int(row['weight']), int(rule['weight'])) - (1 if evidence in (2, 4, 7) else 0))
        con.execute('UPDATE learned_rules SET evidence_count=?,weight=?,enabled=1,source_reason=?,updated_at=? WHERE id=?',
                    (evidence, weight, reason, now, row['id']))
        return int(row['id'])
    cur = con.execute('INSERT INTO learned_rules(scope,term,weight,evidence_count,enabled,source_reason,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?)',
                      (rule['scope'], rule['term'], int(rule['weight']), 1, reason, now, now))
    return int(cur.lastrowid)


def record_feedback(job_key: str, suitability: str, reason: str = '', note: str = '', learn: bool = True) -> dict[str, Any]:
    if suitability not in ('suitable', 'maybe', 'not_suitable'):
        raise ValueError('Invalid suitability')
    ensure_feedback_schema()
    with connection() as con:
        job_row = con.execute('SELECT * FROM jobs WHERE job_key=?', (job_key,)).fetchone()
        if not job_row:
            raise ValueError('Job not found')
        job = dict(job_row)
        rules = _suggest_rules(job, reason) if suitability == 'not_suitable' and learn else []
        created_ids = [_upsert_rule(con, r, reason) for r in rules]
        now = _now()
        con.execute('INSERT INTO job_feedback(job_key,suitability,reason,note,generated_rules_json,created_at) VALUES(?,?,?,?,?,?)',
                    (job_key, suitability, reason, note or '', json.dumps(created_ids), now))
        legacy = {'suitable': 'apply', 'maybe': 'maybe', 'not_suitable': 'skip'}[suitability]
        con.execute('UPDATE jobs SET decision=?,decision_at=? WHERE job_key=?', (legacy, now, job_key))
        if suitability == 'suitable':
            con.execute('''INSERT INTO applications(job_key,status,created_at,updated_at) VALUES(?, 'to_apply', ?, ?)
                           ON CONFLICT(job_key) DO UPDATE SET updated_at=excluded.updated_at''', (job_key, now, now))
    return {'job_key': job_key, 'suitability': suitability, 'reason': reason, 'learned_rule_ids': created_ids}


def list_feedback(limit: int = 100) -> list[dict[str, Any]]:
    ensure_feedback_schema()
    with connection() as con:
        rows = con.execute('''SELECT f.*,j.title,j.company,j.location FROM job_feedback f JOIN jobs j ON j.job_key=f.job_key ORDER BY f.id DESC LIMIT ?''', (limit,)).fetchall()
    return [dict(r) for r in rows]


def list_learned_rules() -> list[dict[str, Any]]:
    ensure_feedback_schema()
    with connection() as con:
        rows = con.execute('SELECT * FROM learned_rules ORDER BY enabled DESC,evidence_count DESC,ABS(weight) DESC,term').fetchall()
    return [{**dict(r), 'enabled': bool(r['enabled'])} for r in rows]


def set_rule_enabled(rule_id: int, enabled: bool) -> None:
    ensure_feedback_schema()
    with connection() as con:
        con.execute('UPDATE learned_rules SET enabled=?,updated_at=? WHERE id=?', (int(enabled), _now(), rule_id))


def delete_rule(rule_id: int) -> None:
    ensure_feedback_schema()
    with connection() as con:
        con.execute('DELETE FROM learned_rules WHERE id=?', (rule_id,))


def apply_learned_penalty(job, base_score: int) -> tuple[int, list[str]]:
    ensure_feedback_schema()
    with connection() as con:
        rules = con.execute('SELECT scope,term,weight,evidence_count FROM learned_rules WHERE enabled=1').fetchall()
    fields = {
        'title': _normalise(getattr(job, 'title', '')),
        'company': _normalise(getattr(job, 'company', '')),
        'location': _normalise(getattr(job, 'location', '')),
        'description': _normalise(f"{getattr(job,'title','')} {getattr(job,'description','')}"),
        'language': getattr(job, 'language_label', '') or '',
    }
    score = int(base_score)
    reasons: list[str] = []
    for r in rules:
        scope, term = r['scope'], r['term']
        if term and term in fields.get(scope, ''):
            score += int(r['weight'])
            reasons.append(f"learned: {scope} '{term}' {r['weight']}")
    return max(0, score), reasons


def feedback_stats() -> dict[str, int]:
    ensure_feedback_schema()
    with connection() as con:
        total = con.execute('SELECT COUNT(*) FROM job_feedback').fetchone()[0]
        unsuitable = con.execute("SELECT COUNT(*) FROM job_feedback WHERE suitability='not_suitable'").fetchone()[0]
        rules = con.execute('SELECT COUNT(*) FROM learned_rules WHERE enabled=1').fetchone()[0]
    return {'feedback_total': total, 'not_suitable': unsuitable, 'active_rules': rules}
