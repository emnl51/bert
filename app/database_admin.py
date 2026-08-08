import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .db import connection, init_db

RESET_SCOPES = {
    'jobs': {
        'label': 'Jobs & Applications',
        'tables': ['job_intelligence','job_feedback','positive_events','job_profile_scores','job_language','search_job_seen','applications','jobs'],
    },
    'runs': {
        'label': 'Run History & Analytics',
        'tables': ['source_run_stats','search_job_runs','search_runs'],
    },
    'learning': {
        'label': 'Learning Data',
        'tables': ['job_feedback','learned_rules','positive_events','positive_rules'],
    },
    'intelligence': {
        'label': 'AI / Intelligence Data',
        'tables': ['job_intelligence'],
    },
}


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def list_user_tables() -> list[str]:
    with connection() as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r['name'] for r in rows]


def database_counts() -> dict[str, int]:
    result = {}
    with connection() as con:
        for table in list_user_tables():
            try:
                result[table] = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            except sqlite3.DatabaseError:
                result[table] = -1
    return result


def backup_database() -> str:
    db_path = Path(settings.database_path)
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f'jobtrack-{_now_stamp()}.db'
    with sqlite3.connect(str(db_path)) as src, sqlite3.connect(str(target)) as dst:
        src.backup(dst)
    os.chmod(target, 0o600)
    return str(target)


def _delete_tables(tables: list[str]) -> dict[str, int]:
    deleted = {}
    with connection() as con:
        con.execute('PRAGMA foreign_keys=OFF')
        existing = {r['name'] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table in tables:
            if table not in existing or table.startswith('sqlite_'):
                continue
            count = int(con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            con.execute(f'DELETE FROM "{table}"')
            deleted[table] = count
            try:
                con.execute('DELETE FROM sqlite_sequence WHERE name=?', (table,))
            except sqlite3.DatabaseError:
                pass
        con.execute('PRAGMA foreign_keys=ON')
    return deleted


def _reseed_factory_defaults() -> None:
    init_db()
    from .profile_store import ensure_profile_schema
    from .search_job_store import ensure_search_job_schema
    from .language_store import ensure_language_schema
    from .feedback_store import ensure_feedback_schema
    from .candidate_store import ensure_candidate_schema
    from .intelligence import ensure_intelligence_schema
    from .source_analytics import ensure_source_analytics_schema
    ensure_profile_schema()
    ensure_search_job_schema()
    ensure_language_schema()
    ensure_feedback_schema()
    ensure_candidate_schema()
    ensure_intelligence_schema()
    ensure_source_analytics_schema()


def reset_database(scope: str, create_backup: bool = True) -> dict:
    valid = set(RESET_SCOPES) | {'operational', 'factory'}
    if scope not in valid:
        raise ValueError('Invalid reset scope')

    backup_path = backup_database() if create_backup else ''
    before = database_counts()

    if scope == 'factory':
        tables = list_user_tables()
    elif scope == 'operational':
        tables = []
        for key in ('jobs','runs','learning','intelligence'):
            tables.extend(RESET_SCOPES[key]['tables'])
        tables = list(dict.fromkeys(tables))
    else:
        tables = RESET_SCOPES[scope]['tables']

    deleted = _delete_tables(tables)
    if scope == 'factory':
        _reseed_factory_defaults()

    return {
        'ok': True,
        'scope': scope,
        'backup_path': backup_path,
        'deleted': deleted,
        'rows_deleted': sum(deleted.values()),
        'before': before,
        'after': database_counts(),
    }
