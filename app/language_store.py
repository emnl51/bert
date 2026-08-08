import json
from datetime import datetime, timezone
from typing import Any

from . import db
from .models import Job


LANGUAGE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS job_language (
    job_key TEXT PRIMARY KEY,
    language_score INTEGER NOT NULL DEFAULT 55,
    overall_score INTEGER NOT NULL DEFAULT 0,
    language_label TEXT NOT NULL DEFAULT 'unclear',
    language_reasons_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_job_language_overall ON job_language(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_language_score ON job_language(language_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_language_label ON job_language(language_label);
'''

LANGUAGE_SETTINGS = {
    'primary_working_language': 'English',
    'current_german_level': 'a2_b1',
    'max_german_requirement': 'b1',
    'min_language_score': '40',
    'language_weight': '35',
    'show_b2_stretch': 'true',
    'hide_german_heavy': 'true',
    'prefer_german_growth': 'true',
}

LANGUAGE_SEARCH_TERMS = (
    'working student supply chain english',
    'werkstudent supply chain english',
    'working student procurement english',
    'werkstudent procurement english',
    'working student supply planning english',
    'operations working student english',
    'order management working student english',
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_language_schema() -> None:
    now = _now()
    with db.connection() as con:
        con.executescript(LANGUAGE_SCHEMA)
        for key, value in LANGUAGE_SETTINGS.items():
            con.execute(
                'INSERT OR IGNORE INTO app_settings(key,value,is_secret,updated_at) VALUES(?,?,0,?)',
                (key, value, now),
            )
        seeded = con.execute("SELECT value FROM app_settings WHERE key='language_search_seeded_v4'").fetchone()
        if not seeded:
            con.executemany(
                "INSERT OR IGNORE INTO keywords(term,kind,weight,enabled) VALUES(?, 'search', 0, 1)",
                [(term,) for term in LANGUAGE_SEARCH_TERMS],
            )
            con.execute(
                "INSERT OR REPLACE INTO app_settings(key,value,is_secret,updated_at) VALUES('language_search_seeded_v4','true',0,?)",
                (now,),
            )


def upsert_language_fit(job: Job) -> None:
    with db.connection() as con:
        con.execute(
            '''INSERT INTO job_language(job_key,language_score,overall_score,language_label,language_reasons_json,updated_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(job_key) DO UPDATE SET
                   language_score=excluded.language_score,
                   overall_score=excluded.overall_score,
                   language_label=excluded.language_label,
                   language_reasons_json=excluded.language_reasons_json,
                   updated_at=excluded.updated_at''',
            (
                job.key, job.language_score, job.overall_score, job.language_label,
                json.dumps(job.language_reasons, ensure_ascii=False), _now(),
            ),
        )


def list_jobs_with_language(
    limit: int = 100,
    min_score: int = 0,
    decision: str | None = None,
    language: str = 'preferred',
    min_language_score: int = 0,
) -> list[dict[str, Any]]:
    where = ['COALESCE(jl.overall_score,j.score) >= ?', 'COALESCE(jl.language_score,55) >= ?']
    params: list[Any] = [min_score, min_language_score]
    if decision == 'active':
        where.append("j.decision != 'skip'")
    elif decision in ('unreviewed', 'apply', 'maybe', 'skip'):
        where.append('j.decision = ?')
        params.append(decision)
    if language == 'preferred':
        where.append("COALESCE(jl.language_label,'unclear') != 'german_heavy'")
    elif language in ('english_first', 'german_growth', 'stretch', 'german_heavy', 'unclear'):
        where.append("COALESCE(jl.language_label,'unclear') = ?")
        params.append(language)
    params.append(limit)

    with db.connection() as con:
        rows = con.execute(
            f'''SELECT j.job_key, j.source, j.title, j.company, j.location, j.url, j.created_at,
                       j.score, j.reasons_json, j.first_seen, j.notified, j.decision, j.decision_at,
                       COALESCE(jl.language_score,55) AS language_score,
                       COALESCE(jl.overall_score,j.score) AS overall_score,
                       COALESCE(jl.language_label,'unclear') AS language_label,
                       COALESCE(jl.language_reasons_json,'[]') AS language_reasons_json,
                       a.status AS application_status, a.applied_at AS application_applied_at
                FROM jobs j
                LEFT JOIN job_language jl ON jl.job_key=j.job_key
                LEFT JOIN applications a ON a.job_key=j.job_key
                WHERE {' AND '.join(where)}
                ORDER BY j.first_seen DESC, COALESCE(jl.overall_score,j.score) DESC LIMIT ?''',
            params,
        ).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item['reasons'] = json.loads(item.pop('reasons_json') or '[]')
        item['language_reasons'] = json.loads(item.pop('language_reasons_json') or '[]')
        item['notified'] = bool(item['notified'])
        result.append(item)
    return result


def enrich_applications(applications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not applications:
        return applications
    keys = [item['job_key'] for item in applications]
    placeholders = ','.join('?' for _ in keys)
    with db.connection() as con:
        rows = con.execute(
            f'''SELECT job_key,language_score,overall_score,language_label
                FROM job_language WHERE job_key IN ({placeholders})''',
            keys,
        ).fetchall()
    language_by_key = {row['job_key']: dict(row) for row in rows}
    result = []
    for item in applications:
        enriched = dict(item)
        lang = language_by_key.get(item['job_key'])
        enriched['language_score'] = lang['language_score'] if lang else 55
        enriched['overall_score'] = lang['overall_score'] if lang else item.get('score', 0)
        enriched['language_label'] = lang['language_label'] if lang else 'unclear'
        result.append(enriched)
    return result
