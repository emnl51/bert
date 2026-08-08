import re
from datetime import datetime, timezone
from typing import Any

from .db import connection

POSITIVE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS positive_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    term TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 4,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    strongest_event TEXT NOT NULL DEFAULT 'suitable',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(scope, term)
);
CREATE INDEX IF NOT EXISTS idx_positive_rules_enabled ON positive_rules(enabled);

CREATE TABLE IF NOT EXISTS positive_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(job_key, event_type),
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_positive_events_job ON positive_events(job_key);
'''

EVENT_STRENGTH = {'suitable': 4, 'applied': 5, 'interview': 9, 'offer': 14}
EVENT_RANK = {'suitable': 1, 'applied': 2, 'interview': 3, 'offer': 4}

STOPWORDS = {
    'werkstudent','working','student','studentin','studentische','m','w','d','f','x','and','und','the','for','für','im','in','of','at','bei',
    'part','time','teilzeit','intern','internship','praktikum','praktikant','praktikantin','junior','senior','manager'
}

SKILL_TERMS = (
    'supply chain','supply planning','demand planning','material planning','procurement','einkauf','purchasing',
    'order management','operations','logistics','logistik','strategic sourcing','sourcing','supplier','lieferant',
    'sap','s/4hana','power bi','excel','erp','inventory','bestand','production planning','produktionsplanung',
    'international','customer','kunde','material','rfq','incoterms'
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_positive_schema() -> None:
    with connection() as con:
        con.executescript(POSITIVE_SCHEMA)


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


def _extract_positive_rules(job: dict[str, Any], language_label: str, event_type: str) -> list[dict[str, Any]]:
    base = EVENT_STRENGTH[event_type]
    rules: list[dict[str, Any]] = []
    for term in _role_terms(job.get('title', '')):
        rules.append({'scope': 'title', 'term': term, 'weight': base})
    text = _normalise(f"{job.get('title','')} {job.get('description','')}")
    matched = [t for t in SKILL_TERMS if t in text]
    for term in matched[:4]:
        rules.append({'scope': 'description', 'term': term, 'weight': max(2, base - 1)})
    if language_label in ('english_first', 'german_growth'):
        rules.append({'scope': 'language', 'term': language_label, 'weight': max(3, base)})
    if event_type in ('interview', 'offer'):
        company = _normalise(job.get('company', ''))
        if company:
            rules.append({'scope': 'company', 'term': company, 'weight': base})
    return rules[:8]


def _upsert_positive_rule(con, rule: dict[str, Any], event_type: str) -> int:
    now = _now()
    row = con.execute('SELECT id,evidence_count,weight,strongest_event FROM positive_rules WHERE scope=? AND term=?',
                      (rule['scope'], rule['term'])).fetchone()
    if row:
        evidence = int(row['evidence_count']) + 1
        strongest = row['strongest_event']
        if EVENT_RANK[event_type] > EVENT_RANK.get(strongest, 0):
            strongest = event_type
        target = max(int(row['weight']), int(rule['weight']))
        if evidence in (2, 4, 7, 12):
            target += 1
        weight = min(30, target)
        con.execute('UPDATE positive_rules SET evidence_count=?,weight=?,enabled=1,strongest_event=?,updated_at=? WHERE id=?',
                    (evidence, weight, strongest, now, row['id']))
        return int(row['id'])
    cur = con.execute('INSERT INTO positive_rules(scope,term,weight,evidence_count,enabled,strongest_event,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?)',
                      (rule['scope'], rule['term'], int(rule['weight']), 1, event_type, now, now))
    return int(cur.lastrowid)


def record_positive_event(job_key: str, event_type: str) -> dict[str, Any]:
    if event_type not in EVENT_STRENGTH:
        raise ValueError('Invalid positive event')
    ensure_positive_schema()
    with connection() as con:
        job_row = con.execute('SELECT * FROM jobs WHERE job_key=?', (job_key,)).fetchone()
        if not job_row:
            raise ValueError('Job not found')
        existing = con.execute('SELECT id FROM positive_events WHERE job_key=? AND event_type=?', (job_key, event_type)).fetchone()
        if existing:
            return {'job_key': job_key, 'event_type': event_type, 'created': False, 'positive_rule_ids': []}
        lang = con.execute('SELECT language_label FROM job_language WHERE job_key=?', (job_key,)).fetchone()
        language_label = lang['language_label'] if lang else 'unclear'
        rules = _extract_positive_rules(dict(job_row), language_label, event_type)
        ids = [_upsert_positive_rule(con, r, event_type) for r in rules]
        con.execute('INSERT INTO positive_events(job_key,event_type,created_at) VALUES(?,?,?)', (job_key, event_type, _now()))
    return {'job_key': job_key, 'event_type': event_type, 'created': True, 'positive_rule_ids': ids}


def sync_application_events() -> int:
    """Import new Applied / Interview / Offer milestones once per job."""
    ensure_positive_schema()
    with connection() as con:
        rows = con.execute("SELECT job_key,status FROM applications WHERE status IN ('applied','interview','offer')").fetchall()
    created = 0
    for row in rows:
        result = record_positive_event(row['job_key'], row['status'])
        if result['created']:
            created += 1
    return created


def list_positive_rules() -> list[dict[str, Any]]:
    ensure_positive_schema()
    with connection() as con:
        rows = con.execute('SELECT * FROM positive_rules ORDER BY enabled DESC,evidence_count DESC,weight DESC,term').fetchall()
    return [{**dict(r), 'enabled': bool(r['enabled'])} for r in rows]


def set_positive_rule_enabled(rule_id: int, enabled: bool) -> None:
    ensure_positive_schema()
    with connection() as con:
        con.execute('UPDATE positive_rules SET enabled=?,updated_at=? WHERE id=?', (int(enabled), _now(), rule_id))


def delete_positive_rule(rule_id: int) -> None:
    ensure_positive_schema()
    with connection() as con:
        con.execute('DELETE FROM positive_rules WHERE id=?', (rule_id,))


def apply_positive_boost(job, base_score: int) -> tuple[int, list[str]]:
    ensure_positive_schema()
    with connection() as con:
        rules = con.execute('SELECT scope,term,weight,evidence_count FROM positive_rules WHERE enabled=1').fetchall()
    fields = {
        'title': _normalise(getattr(job, 'title', '')),
        'company': _normalise(getattr(job, 'company', '')),
        'location': _normalise(getattr(job, 'location', '')),
        'description': _normalise(f"{getattr(job,'title','')} {getattr(job,'description','')}"),
        'language': getattr(job, 'language_label', '') or '',
    }
    score = int(base_score)
    reasons: list[str] = []
    total_boost = 0
    for r in rules:
        if r['term'] and r['term'] in fields.get(r['scope'], ''):
            contribution = int(r['weight'])
            total_boost += contribution
            reasons.append(f"preferred: {r['scope']} '{r['term']}' +{contribution}")
    total_boost = min(30, total_boost)
    return min(100, score + total_boost), reasons


def positive_stats() -> dict[str, int]:
    ensure_positive_schema()
    with connection() as con:
        events = con.execute('SELECT COUNT(*) FROM positive_events').fetchone()[0]
        rules = con.execute('SELECT COUNT(*) FROM positive_rules WHERE enabled=1').fetchone()[0]
        interviews = con.execute("SELECT COUNT(*) FROM positive_events WHERE event_type='interview'").fetchone()[0]
        offers = con.execute("SELECT COUNT(*) FROM positive_events WHERE event_type='offer'").fetchone()[0]
    return {'positive_events': events, 'positive_rules': rules, 'learned_interviews': interviews, 'learned_offers': offers}
