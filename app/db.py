import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from .config import settings
from .models import Job
from .content_language import detect_content_language
from .secrets import decrypt_secret, encrypt_secret


_DATABASE_LOCK = RLock()


@contextmanager
def exclusive_database_access():
    """Serialize database maintenance with ordinary application access.

    SQLite handles concurrent readers and writers, but replacing the database
    file requires every in-process connection to be closed. A re-entrant lock
    lets restore code run migrations that open their own managed connections
    while other request and scheduler threads wait for the replacement to finish.
    """
    with _DATABASE_LOCK:
        yield


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    url TEXT,
    description TEXT,
    created_at TEXT,
    remote INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    decision TEXT NOT NULL DEFAULT 'unreviewed',
    decision_at TEXT,
    content_language TEXT NOT NULL DEFAULT 'unknown',
    content_language_confidence REAL NOT NULL DEFAULT 0,
    content_language_source TEXT NOT NULL DEFAULT 'detected'
);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, key)
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    secrets_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    kind TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(term, kind)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_key TEXT NOT NULL DEFAULT 'admin',
    user_id INTEGER,
    profile_id INTEGER,
    job_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'to_apply',
    applied_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(owner_key, job_key),
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_updated ON applications(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(owner_key, profile_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_job_state (
    owner_key TEXT NOT NULL,
    user_id INTEGER,
    job_key TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'unreviewed',
    decision_at TEXT,
    PRIMARY KEY(owner_key, job_key),
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    fetched INTEGER NOT NULL DEFAULT 0,
    new_matches INTEGER NOT NULL DEFAULT 0,
    provider_errors_json TEXT NOT NULL DEFAULT '[]',
    notification_channels_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT ''
);
"""

DEFAULT_SETTINGS = {
    "target_location": settings.target_location,
    "location_terms": "berlin,potsdam,hennigsdorf,ludwigsfelde,teltow,wildau,schönefeld,schoenefeld,oranienburg,brandenburg",
    "min_score": str(settings.min_score),
    "max_digest_jobs": str(settings.max_digest_jobs),
    "timezone": settings.timezone,
    "schedule_frequency": settings.schedule_frequency,
    "schedule_day": settings.schedule_day,
    "schedule_hour": str(settings.schedule_hour),
    "schedule_minute": str(settings.schedule_minute),
    "schedule_interval_hours": str(settings.schedule_interval_hours),
    "smtp_host": settings.smtp_host,
    "smtp_port": str(settings.smtp_port),
    "smtp_username": settings.smtp_username,
    "smtp_use_tls": str(settings.smtp_use_tls).lower(),
    "email_from": settings.email_from,
    "email_to": settings.email_to,
    "telegram_chat_id": settings.telegram_chat_id,
}

# Legacy seed data for the global keywords table (used by the /api/keywords endpoint
# and the legacy UI). Profile-specific keyword sets live in profile_store.py.
DEFAULT_KEYWORDS = {
    "search": [
        ("werkstudent supply chain", 0),
        ("werkstudent supply planning", 0),
        ("werkstudent procurement", 0),
        ("werkstudent einkauf", 0),
        ("werkstudent order management", 0),
        ("werkstudent operations", 0),
        ("werkstudent logistik", 0),
        ("werkstudent material planning", 0),
        ("werkstudent sales operations", 0),
        ("working student supply chain", 0),
    ],
    "title": [
        ("supply chain", 32),
        ("supply planning", 32),
        ("demand planning", 28),
        ("material planning", 28),
        ("procurement", 30),
        ("einkauf", 30),
        ("purchasing", 28),
        ("order management", 28),
        ("operations", 22),
        ("logistics", 24),
        ("logistik", 24),
        ("sales operations", 25),
        ("customer operations", 24),
        ("strategic sourcing", 25),
    ],
    "format": [
        ("werkstudent", 30),
        ("working student", 30),
        ("studentische aushilfe", 25),
        ("student assistant", 25),
        ("teilzeit", 12),
        ("part-time", 12),
        ("part time", 12),
        ("minijob", 8),
    ],
    "skill": [
        ("sap", 7),
        ("s/4hana", 7),
        ("power bi", 6),
        ("excel", 4),
        ("supplier", 5),
        ("lieferant", 5),
        ("inventory", 5),
        ("bestand", 5),
        ("incoterms", 5),
        ("erp", 5),
        ("production planning", 7),
        ("produktionsplanung", 7),
        ("international", 4),
        ("customer", 4),
        ("kunde", 4),
        ("material", 4),
        ("rfq", 5),
        ("sourcing", 5),
    ],
    "negative": [
        ("software engineer", -30),
        ("developer", -25),
        ("nurse", -50),
        ("pflege", -50),
        ("driver", -35),
        ("fahrer", -35),
        ("restaurant", -35),
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_key(user_id: int | None) -> str:
    return "admin" if user_id is None else f"user:{int(user_id)}"


def _migrate_application_ownership(con) -> None:
    columns = {row[1] for row in con.execute("PRAGMA table_info(applications)").fetchall()}
    if not columns or "owner_key" in columns:
        return
    con.execute("ALTER TABLE applications RENAME TO applications_legacy_v18")
    con.execute(
        """CREATE TABLE applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,owner_key TEXT NOT NULL DEFAULT 'admin',user_id INTEGER,profile_id INTEGER,job_key TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'to_apply',applied_at TEXT,notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(owner_key,job_key),
        FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE)"""
    )
    con.execute(
        """INSERT INTO applications(owner_key,user_id,profile_id,job_key,status,applied_at,notes,created_at,updated_at)
        SELECT 'admin',NULL,NULL,job_key,status,applied_at,notes,created_at,updated_at FROM applications_legacy_v18"""
    )
    con.execute("DROP TABLE applications_legacy_v18")
    con.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_applications_updated ON applications(updated_at DESC)")
    con.execute(
        """INSERT OR IGNORE INTO user_job_state(owner_key,user_id,job_key,decision,decision_at)
        SELECT 'admin',NULL,job_key,decision,decision_at FROM jobs WHERE decision!='unreviewed'"""
    )


def _secure_database_file() -> None:
    """Restrict SQLite file permissions to owner-only (0600).

    The Docker container runs as the jobtrack user, but host-side volume mounts
    can expose more permissive defaults. This narrows permissions on every init
    so the database and its WAL/SHM sidecars are not world-readable.
    """
    path = settings.database_path
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    for suffix in ("-wal", "-shm"):
        sidecar = f"{path}{suffix}"
        try:
            os.chmod(sidecar, 0o600)
        except OSError:
            pass


def init_db() -> None:
    with exclusive_database_access():
        _init_db_unlocked()


def _init_db_unlocked() -> None:
    folder = os.path.dirname(settings.database_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with _connect() as con:
        con.executescript(SCHEMA)
        _migrate_application_ownership(con)
        application_columns = {row[1] for row in con.execute("PRAGMA table_info(applications)").fetchall()}
        if "profile_id" not in application_columns:
            # Existing records have no reliable origin profile. Keep them unassigned
            # instead of guessing from a shared job or later feedback.
            con.execute("ALTER TABLE applications ADD COLUMN profile_id INTEGER")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(owner_key, profile_id, updated_at DESC)"
        )
        # Lightweight in-place migration for databases created by v1/v2.
        job_columns = {row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()}
        if "decision" not in job_columns:
            con.execute("ALTER TABLE jobs ADD COLUMN decision TEXT NOT NULL DEFAULT 'unreviewed'")
        if "decision_at" not in job_columns:
            con.execute("ALTER TABLE jobs ADD COLUMN decision_at TEXT")
        if "content_language" not in job_columns:
            con.execute("ALTER TABLE jobs ADD COLUMN content_language TEXT NOT NULL DEFAULT 'unknown'")
        if "content_language_confidence" not in job_columns:
            con.execute("ALTER TABLE jobs ADD COLUMN content_language_confidence REAL NOT NULL DEFAULT 0")
        if "content_language_source" not in job_columns:
            con.execute("ALTER TABLE jobs ADD COLUMN content_language_source TEXT NOT NULL DEFAULT 'detected'")
        rows = con.execute(
            "SELECT job_key,title,description FROM jobs WHERE content_language='unknown' AND content_language_source='detected'"
        ).fetchall()
        for row in rows:
            detected = detect_content_language(row["title"], row["description"])
            con.execute(
                "UPDATE jobs SET content_language=?,content_language_confidence=? WHERE job_key=?",
                (detected.code, detected.confidence, row["job_key"]),
            )
        now = _now()
        for key, value in DEFAULT_SETTINGS.items():
            con.execute(
                "INSERT OR IGNORE INTO app_settings(key,value,is_secret,updated_at) VALUES(?,?,0,?)",
                (key, value, now),
            )
        source_count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        if source_count == 0:
            con.execute(
                "INSERT INTO sources(name,source_type,enabled,config_json,secrets_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                ("Arbeitnow", "arbeitnow", 1, json.dumps({"pages": settings.arbeitnow_pages}), "{}", now, now),
            )
            adz_secrets = {}
            if settings.adzuna_app_id:
                adz_secrets["app_id"] = encrypt_secret(settings.adzuna_app_id)
            if settings.adzuna_app_key:
                adz_secrets["app_key"] = encrypt_secret(settings.adzuna_app_key)
            con.execute(
                "INSERT INTO sources(name,source_type,enabled,config_json,secrets_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (
                    "Adzuna",
                    "adzuna",
                    0,
                    json.dumps(
                        {"distance_km": settings.adzuna_distance_km, "results_per_term": settings.results_per_term}
                    ),
                    json.dumps(adz_secrets),
                    now,
                    now,
                ),
            )
        keyword_count = con.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
        if keyword_count == 0:
            for kind, items in DEFAULT_KEYWORDS.items():
                con.executemany(
                    "INSERT OR IGNORE INTO keywords(term,kind,weight,enabled) VALUES(?,?,?,1)",
                    [(term, kind, weight) for term, weight in items],
                )


@contextmanager
def connection():
    with _DATABASE_LOCK:
        con = _connect()
        try:
            yield con
            con.commit()
        finally:
            con.close()


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(settings.database_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def set_setting(key: str, value: str, is_secret: bool = False, user_id: int | None = None) -> None:
    stored = encrypt_secret(value) if is_secret and value else value
    with connection() as con:
        if user_id is None:
            con.execute(
                """INSERT INTO app_settings(key,value,is_secret,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,is_secret=excluded.is_secret,updated_at=excluded.updated_at""",
                (key, stored, int(is_secret), _now()),
            )
        else:
            con.execute(
                """INSERT INTO user_settings(user_id,key,value,is_secret,updated_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value,is_secret=excluded.is_secret,
                   updated_at=excluded.updated_at""",
                (user_id, key, stored, int(is_secret), _now()),
            )


def get_setting(key: str, default: str = "", reveal_secret: bool = True, user_id: int | None = None) -> str:
    with connection() as con:
        if user_id is None:
            row = con.execute("SELECT value,is_secret FROM app_settings WHERE key=?", (key,)).fetchone()
        else:
            row = con.execute(
                "SELECT value,is_secret FROM user_settings WHERE user_id=? AND key=?", (user_id, key)
            ).fetchone()
    if not row:
        return default
    value = row["value"] or ""
    if row["is_secret"]:
        return decrypt_secret(value) if reveal_secret else ("configured" if value else "")
    return value


def get_all_settings(mask_secrets: bool = True, user_id: int | None = None) -> dict[str, str]:
    with connection() as con:
        if user_id is None:
            rows = con.execute("SELECT key,value,is_secret FROM app_settings ORDER BY key").fetchall()
        else:
            rows = con.execute(
                "SELECT key,value,is_secret FROM user_settings WHERE user_id=? ORDER BY key", (user_id,)
            ).fetchall()
    result = dict(DEFAULT_SETTINGS) if user_id is not None else {}
    if user_id is not None:
        # Never expose administrator/environment notification identities as a
        # new user's defaults. Each account configures its own delivery data.
        for key in ("smtp_host", "smtp_username", "email_from", "email_to", "telegram_chat_id"):
            result[key] = ""
    for row in rows:
        if row["is_secret"]:
            result[row["key"]] = (
                "configured"
                if (mask_secrets and row["value"])
                else (decrypt_secret(row["value"]) if row["value"] else "")
            )
        else:
            result[row["key"]] = row["value"]
    return result


def list_sources(mask_secrets: bool = True) -> list[dict[str, Any]]:
    with connection() as con:
        rows = con.execute("SELECT * FROM sources ORDER BY id").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        item["config"] = json.loads(item.pop("config_json") or "{}")
        encrypted = json.loads(item.pop("secrets_json") or "{}")
        if mask_secrets:
            item["secrets"] = {k: ("configured" if v else "") for k, v in encrypted.items()}
        else:
            item["secrets"] = {k: decrypt_secret(v) for k, v in encrypted.items()}
        result.append(item)
    return result


def get_source(source_id: int, mask_secrets: bool = False) -> dict[str, Any] | None:
    with connection() as con:
        row = con.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["config"] = json.loads(item.pop("config_json") or "{}")
    encrypted = json.loads(item.pop("secrets_json") or "{}")
    item["secrets"] = (
        {k: ("configured" if v else "") for k, v in encrypted.items()}
        if mask_secrets
        else {k: decrypt_secret(v) for k, v in encrypted.items()}
    )
    return item


def save_source(
    name: str, source_type: str, enabled: bool, config: dict, secrets: dict, source_id: int | None = None
) -> int:
    now = _now()
    with connection() as con:
        if source_id:
            existing = con.execute("SELECT secrets_json FROM sources WHERE id=?", (source_id,)).fetchone()
            if not existing:
                raise ValueError("Source not found")
            existing_secrets = json.loads(existing["secrets_json"] or "{}")
            for key, value in secrets.items():
                if value:
                    existing_secrets[key] = encrypt_secret(value)
            con.execute(
                "UPDATE sources SET name=?,source_type=?,enabled=?,config_json=?,secrets_json=?,updated_at=? WHERE id=?",
                (name, source_type, int(enabled), json.dumps(config), json.dumps(existing_secrets), now, source_id),
            )
            return source_id
        encrypted = {k: encrypt_secret(v) for k, v in secrets.items() if v}
        cur = con.execute(
            "INSERT INTO sources(name,source_type,enabled,config_json,secrets_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (name, source_type, int(enabled), json.dumps(config), json.dumps(encrypted), now, now),
        )
        return int(cur.lastrowid)


def delete_source(source_id: int) -> None:
    with connection() as con:
        row = con.execute("SELECT source_type FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            return
        if row["source_type"] in ("arbeitnow", "adzuna"):
            raise ValueError("Built-in sources can be disabled but not deleted")
        con.execute("DELETE FROM sources WHERE id=?", (source_id,))


def list_keywords(kind: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT id,term,kind,weight,enabled FROM keywords"
    params: tuple = ()
    if kind:
        sql += " WHERE kind=?"
        params = (kind,)
    sql += " ORDER BY kind, weight DESC, term"
    with connection() as con:
        rows = con.execute(sql, params).fetchall()
    return [{**dict(r), "enabled": bool(r["enabled"])} for r in rows]


def save_keyword(term: str, kind: str, weight: int, enabled: bool, keyword_id: int | None = None) -> int:
    with connection() as con:
        if keyword_id:
            con.execute(
                "UPDATE keywords SET term=?,kind=?,weight=?,enabled=? WHERE id=?",
                (term.strip().lower(), kind, weight, int(enabled), keyword_id),
            )
            return keyword_id
        cur = con.execute(
            "INSERT INTO keywords(term,kind,weight,enabled) VALUES(?,?,?,?)",
            (term.strip().lower(), kind, weight, int(enabled)),
        )
        return int(cur.lastrowid)


def delete_keyword(keyword_id: int) -> None:
    with connection() as con:
        con.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))


def active_keyword_map() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {"search": {}, "title": {}, "format": {}, "skill": {}, "negative": {}}
    for item in list_keywords():
        if item["enabled"]:
            result.setdefault(item["kind"], {})[item["term"]] = item["weight"]
    return result


def upsert_job(job: Job) -> bool:
    now = job.seen_at
    detected = detect_content_language(job.title, job.description)
    with connection() as con:
        existing = con.execute(
            "SELECT job_key,content_language_source FROM jobs WHERE job_key=?", (job.key,)
        ).fetchone()
        if existing:
            language_sql = ""
            language_params = ()
            if existing["content_language_source"] != "manual":
                language_sql = ", content_language=?, content_language_confidence=?, content_language_source='detected'"
                language_params = (detected.code, detected.confidence)
            con.execute(
                f"""UPDATE jobs SET title=?, company=?, location=?, url=?, description=?, created_at=?,
                   remote=?, score=?, reasons_json=?, last_seen=?{language_sql} WHERE job_key=?""",
                (
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.description,
                    job.created_at,
                    int(job.remote),
                    job.score,
                    json.dumps(job.reasons, ensure_ascii=False),
                    now,
                    *language_params,
                    job.key,
                ),
            )
            return False
        con.execute(
            """INSERT INTO jobs(job_key, source, external_id, title, company, location, url,
               description, created_at, remote, score, reasons_json, first_seen, last_seen, notified,
               content_language, content_language_confidence, content_language_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'detected')""",
            (
                job.key,
                job.source,
                job.external_id,
                job.title,
                job.company,
                job.location,
                job.url,
                job.description,
                job.created_at,
                int(job.remote),
                job.score,
                json.dumps(job.reasons, ensure_ascii=False),
                now,
                now,
                detected.code,
                detected.confidence,
            ),
        )
        return True


def set_job_content_language(job_key: str, code: str) -> dict[str, Any]:
    if code not in ("de", "en", "mixed", "unknown", "auto"):
        raise ValueError("Invalid content language")
    with connection() as con:
        row = con.execute("SELECT title,description FROM jobs WHERE job_key=?", (job_key,)).fetchone()
        if not row:
            raise ValueError("Job not found")
        if code == "auto":
            detected = detect_content_language(row["title"], row["description"])
            code, confidence, source = detected.code, detected.confidence, "detected"
        else:
            confidence, source = 1.0, "manual"
        con.execute(
            "UPDATE jobs SET content_language=?,content_language_confidence=?,content_language_source=? WHERE job_key=?",
            (code, confidence, source, job_key),
        )
    return {
        "job_key": job_key,
        "content_language": code,
        "content_language_confidence": confidence,
        "content_language_source": source,
    }


def mark_notified(keys: list[str]) -> None:
    if not keys:
        return
    with connection() as con:
        con.executemany("UPDATE jobs SET notified=1 WHERE job_key=?", [(k,) for k in keys])


def list_jobs(limit: int = 100, min_score: int = 0, decision: str | None = None) -> list[dict]:
    where = ["score >= ?"]
    params: list[Any] = [min_score]
    if decision == "active":
        where.append("decision != 'skip'")
    elif decision in ("unreviewed", "apply", "maybe", "skip"):
        where.append("decision = ?")
        params.append(decision)
    params.append(limit)
    with connection() as con:
        rows = con.execute(
            f"""SELECT job_key, source, title, company, location, url, created_at, score,
                      reasons_json, first_seen, notified, decision, decision_at
               FROM jobs WHERE {" AND ".join(where)}
               ORDER BY first_seen DESC, score DESC LIMIT ?""",
            params,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        item["notified"] = bool(item["notified"])
        result.append(item)
    return result


VALID_DECISIONS = {"unreviewed", "apply", "maybe", "skip"}
VALID_APPLICATION_STATUSES = {"to_apply", "applied", "interview", "rejected", "offer"}


def set_job_decision(
    job_key: str, decision: str, user_id: int | None = None, profile_id: int | None = None
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid decision")
    now = _now()
    owner = _owner_key(user_id)
    with connection() as con:
        job = con.execute("SELECT job_key FROM jobs WHERE job_key=?", (job_key,)).fetchone()
        if not job:
            raise ValueError("Job not found")
        con.execute(
            """INSERT INTO user_job_state(owner_key,user_id,job_key,decision,decision_at) VALUES(?,?,?,?,?)
               ON CONFLICT(owner_key,job_key) DO UPDATE SET decision=excluded.decision,decision_at=excluded.decision_at""",
            (owner, user_id, job_key, decision, now),
        )
        if user_id is None:
            con.execute("UPDATE jobs SET decision=?, decision_at=? WHERE job_key=?", (decision, now, job_key))
        app = con.execute(
            "SELECT status FROM applications WHERE owner_key=? AND job_key=?", (owner, job_key)
        ).fetchone()
        if decision == "apply" and not app:
            con.execute(
                """INSERT INTO applications(owner_key,user_id,profile_id,job_key,status,applied_at,notes,created_at,updated_at)
                   VALUES(?,?,?,?,'to_apply',NULL,'',?,?)""",
                (owner, user_id, profile_id, job_key, now, now),
            )
        elif decision != "apply" and app and app["status"] == "to_apply":
            # If it was only queued and never actually applied, remove it from the tracker.
            con.execute("DELETE FROM applications WHERE owner_key=? AND job_key=?", (owner, job_key))
    return {"job_key": job_key, "decision": decision, "decision_at": now}


def save_application(
    job_key: str,
    status: str,
    notes: str | None = None,
    applied_at: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    if status not in VALID_APPLICATION_STATUSES:
        raise ValueError("Invalid application status")
    now = _now()
    owner = _owner_key(user_id)
    with connection() as con:
        job = con.execute("SELECT job_key FROM jobs WHERE job_key=?", (job_key,)).fetchone()
        if not job:
            raise ValueError("Job not found")
        current = con.execute("SELECT * FROM applications WHERE owner_key=? AND job_key=?", (owner, job_key)).fetchone()
        current_notes = current["notes"] if current else ""
        current_applied_at = current["applied_at"] if current else None
        final_notes = current_notes if notes is None else notes
        final_applied_at = current_applied_at if applied_at is None else (applied_at or None)
        if status != "to_apply" and not final_applied_at:
            # First movement beyond To Apply is treated as the application date.
            final_applied_at = now
        if current:
            con.execute(
                "UPDATE applications SET status=?, applied_at=?, notes=?, updated_at=? WHERE owner_key=? AND job_key=?",
                (status, final_applied_at, final_notes, now, owner, job_key),
            )
        else:
            con.execute(
                """INSERT INTO applications(owner_key,user_id,job_key,status,applied_at,notes,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (owner, user_id, job_key, status, final_applied_at, final_notes, now, now),
            )
        con.execute(
            """INSERT INTO user_job_state(owner_key,user_id,job_key,decision,decision_at) VALUES(?,?,?,'apply',?)
               ON CONFLICT(owner_key,job_key) DO UPDATE SET decision='apply',decision_at=excluded.decision_at""",
            (owner, user_id, job_key, now),
        )
        if user_id is None:
            con.execute("UPDATE jobs SET decision='apply', decision_at=? WHERE job_key=?", (now, job_key))
    return {
        "job_key": job_key,
        "status": status,
        "applied_at": final_applied_at,
        "notes": final_notes,
        "updated_at": now,
    }


def list_applications(
    status: str | None = None,
    limit: int = 300,
    user_id: int | None = None,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    where = "WHERE a.owner_key=?"
    params: list[Any] = [_owner_key(user_id)]
    if status in VALID_APPLICATION_STATUSES:
        where += " AND a.status=?"
        params.append(status)
    if profile_id is not None:
        where += " AND a.profile_id=?"
        params.append(profile_id)
    params.append(limit)
    with connection() as con:
        rows = con.execute(
            f"""SELECT a.job_key, a.status, a.applied_at, a.notes, a.created_at, a.updated_at,
                       j.title, j.company, j.location, j.url, j.source, j.score,
                       a.profile_id,
                       COALESCE(s.decision,'unreviewed') AS decision
                FROM applications a JOIN jobs j ON j.job_key=a.job_key
                LEFT JOIN user_job_state s ON s.owner_key=a.owner_key AND s.job_key=a.job_key
                {where}
                ORDER BY CASE a.status
                    WHEN 'interview' THEN 1 WHEN 'offer' THEN 2 WHEN 'to_apply' THEN 3
                    WHEN 'applied' THEN 4 WHEN 'rejected' THEN 5 ELSE 9 END,
                    a.updated_at DESC LIMIT ?""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def application_stats(user_id: int | None = None, profile_id: int | None = None) -> dict[str, int]:
    where = "WHERE owner_key=?"
    params: list[Any] = [_owner_key(user_id)]
    if profile_id is not None:
        where += " AND profile_id=?"
        params.append(profile_id)
    with connection() as con:
        rows = con.execute(
            f"SELECT status, COUNT(*) AS n FROM applications {where} GROUP BY status",
            params,
        ).fetchall()
    result = {status: 0 for status in VALID_APPLICATION_STATUSES}
    for row in rows:
        result[row["status"]] = row["n"]
    result["total"] = sum(result.values())
    result["active"] = result["to_apply"] + result["applied"] + result["interview"] + result["offer"]
    return result


def create_run() -> int:
    with connection() as con:
        cur = con.execute("INSERT INTO search_runs(started_at,status) VALUES(?,?)", (_now(), "running"))
        return int(cur.lastrowid)


def finish_run(
    run_id: int,
    *,
    status: str,
    fetched: int = 0,
    new_matches: int = 0,
    provider_errors: list[str] | None = None,
    notification_channels: list[str] | None = None,
    error: str = "",
) -> None:
    with connection() as con:
        con.execute(
            """UPDATE search_runs SET finished_at=?,status=?,fetched=?,new_matches=?,provider_errors_json=?,
               notification_channels_json=?,error=? WHERE id=?""",
            (
                _now(),
                status,
                fetched,
                new_matches,
                json.dumps(provider_errors or []),
                json.dumps(notification_channels or []),
                error,
                run_id,
            ),
        )


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    with connection() as con:
        rows = con.execute("SELECT * FROM search_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["provider_errors"] = json.loads(item.pop("provider_errors_json") or "[]")
        item["notification_channels"] = json.loads(item.pop("notification_channels_json") or "[]")
        result.append(item)
    return result


def dashboard_stats() -> dict[str, int]:
    with connection() as con:
        jobs = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        notified = con.execute("SELECT COUNT(*) FROM jobs WHERE notified=1").fetchone()[0]
        reviewed = con.execute("SELECT COUNT(*) FROM jobs WHERE decision != 'unreviewed'").fetchone()[0]
        enabled_sources = con.execute("SELECT COUNT(*) FROM sources WHERE enabled=1").fetchone()[0]
    apps = application_stats()
    return {
        "jobs": jobs,
        "notified": notified,
        "reviewed": reviewed,
        "enabled_sources": enabled_sources,
        "to_apply": apps["to_apply"],
        "applications_active": apps["active"],
        "interviews": apps["interview"],
        "offers": apps["offer"],
    }
