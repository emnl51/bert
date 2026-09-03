import json
from datetime import datetime, timedelta, timezone
from typing import Any
from .db import connection
from .secrets import encrypt_secret, decrypt_secret

SEARCH_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    profile_id INTEGER NOT NULL,
    inherit_location INTEGER NOT NULL DEFAULT 0,
    target_location TEXT NOT NULL DEFAULT 'Berlin',
    location_terms_json TEXT NOT NULL DEFAULT '[]',
    search_terms_json TEXT NOT NULL DEFAULT '[]',
    allowlist_terms_json TEXT,
    blocklist_terms_json TEXT,
    allowlist_boost INTEGER NOT NULL DEFAULT 15,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    frequency TEXT NOT NULL DEFAULT 'weekly',
    day_of_week TEXT NOT NULL DEFAULT 'mon',
    hour INTEGER NOT NULL DEFAULT 8,
    minute INTEGER NOT NULL DEFAULT 0,
    interval_hours INTEGER NOT NULL DEFAULT 12,
    min_score_override INTEGER,
    min_language_score_override INTEGER,
    employment_mode TEXT NOT NULL DEFAULT 'prefer',
    min_cv_match INTEGER NOT NULL DEFAULT 58,
    max_results INTEGER NOT NULL DEFAULT 20,
    notify_telegram INTEGER NOT NULL DEFAULT 0,
    notify_email INTEGER NOT NULL DEFAULT 0,
    notification_json TEXT NOT NULL DEFAULT '{}',
    secrets_json TEXT NOT NULL DEFAULT '{}',
    last_run_at TEXT,
    last_run_status TEXT,
    last_match_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, name),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES search_profiles(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_search_jobs_enabled ON search_jobs(enabled);

CREATE TABLE IF NOT EXISTS search_job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_job_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    fetched INTEGER NOT NULL DEFAULT 0,
    matches INTEGER NOT NULL DEFAULT 0,
    provider_errors_json TEXT NOT NULL DEFAULT '[]',
    notification_channels_json TEXT NOT NULL DEFAULT '[]',
    filter_counts_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_search_job_runs_job ON search_job_runs(search_job_id,id DESC);

CREATE TABLE IF NOT EXISTS search_job_seen (
    search_job_id INTEGER NOT NULL,
    job_key TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY(search_job_id,job_key),
    FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_search_job_seen_job ON search_job_seen(job_key);

CREATE TABLE IF NOT EXISTS search_job_locks (
    search_job_id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE
);
"""

SECRET_FIELDS = {"telegram_bot_token", "smtp_password"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_terms(values: list[Any] | None) -> list[str] | None:
    if values is None:
        return None
    terms = []
    seen = set()
    for value in values:
        term = " ".join(str(value).strip().lower().split())
        if term and term not in seen:
            terms.append(term)
            seen.add(term)
    return terms


def _migrate_search_job_ownership(con) -> None:
    columns = {row[1] for row in con.execute("PRAGMA table_info(search_jobs)").fetchall()}
    if not columns or "user_id" in columns:
        return
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """CREATE TABLE search_jobs_v18 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,profile_id INTEGER NOT NULL,
            inherit_location INTEGER NOT NULL DEFAULT 0,target_location TEXT NOT NULL DEFAULT 'Berlin',
            location_terms_json TEXT NOT NULL DEFAULT '[]',search_terms_json TEXT NOT NULL DEFAULT '[]',
            allowlist_terms_json TEXT,blocklist_terms_json TEXT,allowlist_boost INTEGER NOT NULL DEFAULT 15,
            source_ids_json TEXT NOT NULL DEFAULT '[]',frequency TEXT NOT NULL DEFAULT 'weekly',
            day_of_week TEXT NOT NULL DEFAULT 'mon',hour INTEGER NOT NULL DEFAULT 8,minute INTEGER NOT NULL DEFAULT 0,
            interval_hours INTEGER NOT NULL DEFAULT 12,min_score_override INTEGER,min_language_score_override INTEGER,
            min_cv_match INTEGER NOT NULL DEFAULT 58,
            max_results INTEGER NOT NULL DEFAULT 20,notify_telegram INTEGER NOT NULL DEFAULT 0,
            notify_email INTEGER NOT NULL DEFAULT 0,notification_json TEXT NOT NULL DEFAULT '{}',
            secrets_json TEXT NOT NULL DEFAULT '{}',last_run_at TEXT,last_run_status TEXT,
            last_match_count INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            UNIQUE(user_id,name),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(profile_id) REFERENCES search_profiles(id) ON DELETE RESTRICT)"""
        )
        con.execute(
            """INSERT INTO search_jobs_v18
            (id,user_id,name,enabled,profile_id,inherit_location,target_location,location_terms_json,
             search_terms_json,allowlist_terms_json,blocklist_terms_json,allowlist_boost,source_ids_json,
             frequency,day_of_week,hour,minute,interval_hours,min_score_override,min_language_score_override,min_cv_match,
             max_results,notify_telegram,notify_email,notification_json,secrets_json,last_run_at,last_run_status,
             last_match_count,created_at,updated_at)
            SELECT id,NULL,name,enabled,profile_id,COALESCE(inherit_location,0),target_location,location_terms_json,
             COALESCE(search_terms_json,'[]'),allowlist_terms_json,blocklist_terms_json,COALESCE(allowlist_boost,15),
             source_ids_json,frequency,day_of_week,hour,minute,interval_hours,min_score_override,
             min_language_score_override,58,max_results,notify_telegram,notify_email,notification_json,secrets_json,
             last_run_at,last_run_status,last_match_count,created_at,updated_at FROM search_jobs"""
        )
        con.execute("DROP TABLE search_jobs")
        con.execute("ALTER TABLE search_jobs_v18 RENAME TO search_jobs")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


def ensure_search_job_schema(user_id: int | None = None) -> None:
    from .profile_store import ensure_profile_schema, get_profile

    ensure_profile_schema(user_id)
    p = get_profile(user_id=user_id)
    with connection() as con:
        con.executescript(SEARCH_JOB_SCHEMA)
        _migrate_search_job_ownership(con)
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_jobs_enabled ON search_jobs(user_id,enabled)")
        columns = {row[1] for row in con.execute("PRAGMA table_info(search_jobs)").fetchall()}
        if "search_terms_json" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN search_terms_json TEXT NOT NULL DEFAULT '[]'")
        if "inherit_location" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN inherit_location INTEGER NOT NULL DEFAULT 0")
        if "allowlist_terms_json" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN allowlist_terms_json TEXT")
        if "blocklist_terms_json" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN blocklist_terms_json TEXT")
        if "allowlist_boost" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN allowlist_boost INTEGER NOT NULL DEFAULT 15")
        if "min_cv_match" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN min_cv_match INTEGER NOT NULL DEFAULT 58")
        if "employment_mode" not in columns:
            con.execute("ALTER TABLE search_jobs ADD COLUMN employment_mode TEXT NOT NULL DEFAULT 'prefer'")
        run_columns = {row[1] for row in con.execute("PRAGMA table_info(search_job_runs)").fetchall()}
        if "filter_counts_json" not in run_columns:
            con.execute("ALTER TABLE search_job_runs ADD COLUMN filter_counts_json TEXT NOT NULL DEFAULT '{}'")
        if con.execute("SELECT COUNT(*) FROM search_jobs WHERE user_id IS ?", (user_id,)).fetchone()[0] == 0 and p:
            now = _now()
            con.execute(
                """INSERT INTO search_jobs(user_id,name,enabled,profile_id,target_location,location_terms_json,source_ids_json,frequency,day_of_week,hour,minute,interval_hours,max_results,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    "Werkstudent Berlin Weekly",
                    1,
                    p["id"],
                    p["target_location"],
                    json.dumps(p["location_terms"]),
                    json.dumps([]),
                    "weekly",
                    "mon",
                    8,
                    0,
                    12,
                    20,
                    now,
                    now,
                ),
            )


def _decode(row, mask_secrets: bool) -> dict[str, Any]:
    d = dict(row)
    for k in ("enabled", "inherit_location", "notify_telegram", "notify_email"):
        d[k] = bool(d[k])
    d["location_terms"] = json.loads(d.pop("location_terms_json") or "[]")
    d["search_terms"] = json.loads(d.pop("search_terms_json") or "[]")
    allowlist_json = d.pop("allowlist_terms_json")
    blocklist_json = d.pop("blocklist_terms_json")
    d["allowlist_terms"] = json.loads(allowlist_json) if allowlist_json is not None else None
    d["blocklist_terms"] = json.loads(blocklist_json) if blocklist_json is not None else None
    d["source_ids"] = json.loads(d.pop("source_ids_json") or "[]")
    d["notification"] = json.loads(d.pop("notification_json") or "{}")
    enc = json.loads(d.pop("secrets_json") or "{}")
    d["secrets"] = {k: ("configured" if mask_secrets and v else decrypt_secret(v)) for k, v in enc.items()}
    return d


def list_search_jobs(mask_secrets: bool = True, user_id: int | None = None) -> list[dict[str, Any]]:
    ensure_search_job_schema(user_id)
    with connection() as con:
        rows = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj JOIN search_profiles sp ON sp.id=sj.profile_id
               WHERE sj.user_id IS ? AND sp.user_id IS ? ORDER BY sj.enabled DESC,sj.id""",
            (user_id, user_id),
        ).fetchall()
    return [_decode(r, mask_secrets) for r in rows]


def list_all_search_jobs(mask_secrets: bool = True) -> list[dict[str, Any]]:
    """Scheduler-only view across owners; never expose this through a user API."""
    ensure_search_job_schema()
    with connection() as con:
        rows = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj
               JOIN search_profiles sp ON sp.id=sj.profile_id ORDER BY sj.enabled DESC,sj.id"""
        ).fetchall()
    return [_decode(row, mask_secrets) for row in rows]


def get_search_job(job_id: int, mask_secrets: bool = False, user_id: int | None = None) -> dict[str, Any] | None:
    ensure_search_job_schema(user_id)
    with connection() as con:
        row = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj JOIN search_profiles sp ON sp.id=sj.profile_id
               WHERE sj.id=? AND sj.user_id IS ? AND sp.user_id IS ?""",
            (job_id, user_id, user_id),
        ).fetchone()
    return _decode(row, mask_secrets) if row else None


def get_search_job_any(job_id: int, mask_secrets: bool = False) -> dict[str, Any] | None:
    """Worker-only lookup by globally unique id."""
    ensure_search_job_schema()
    with connection() as con:
        row = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj
               JOIN search_profiles sp ON sp.id=sj.profile_id WHERE sj.id=?""",
            (job_id,),
        ).fetchone()
    return _decode(row, mask_secrets) if row else None


def save_search_job(data: dict[str, Any], job_id: int | None = None, user_id: int | None = None) -> int:
    ensure_search_job_schema(user_id)
    now = _now()
    notification = dict(data.get("notification") or {})
    supplied_secrets = dict(data.get("secrets") or {})
    with connection() as con:
        profile = con.execute(
            "SELECT id FROM search_profiles WHERE id=? AND user_id IS ?", (int(data["profile_id"]), user_id)
        ).fetchone()
        if not profile:
            raise ValueError("Profile not found")
        existing_secrets = {}
        if job_id:
            row = con.execute(
                "SELECT secrets_json FROM search_jobs WHERE id=? AND user_id IS ?", (job_id, user_id)
            ).fetchone()
            if not row:
                raise ValueError("Search job not found")
            existing_secrets = json.loads(row["secrets_json"] or "{}")
        for key, value in supplied_secrets.items():
            if key in SECRET_FIELDS and value and value != "configured":
                existing_secrets[key] = encrypt_secret(value)
        search_terms = _normalise_terms(data.get("search_terms") or []) or []
        allowlist_terms = _normalise_terms(data.get("allowlist_terms"))
        blocklist_terms = _normalise_terms(data.get("blocklist_terms"))
        vals = {
            "user_id": user_id,
            "name": str(data.get("name", "Search Job")).strip(),
            "enabled": int(bool(data.get("enabled", True))),
            "profile_id": int(data["profile_id"]),
            "inherit_location": int(bool(data.get("inherit_location", False))),
            "target_location": str(data.get("target_location", "Berlin")),
            "location_terms_json": json.dumps(data.get("location_terms", []), ensure_ascii=False),
            "search_terms_json": json.dumps(search_terms, ensure_ascii=False),
            "allowlist_terms_json": (
                None if allowlist_terms is None else json.dumps(allowlist_terms, ensure_ascii=False)
            ),
            "blocklist_terms_json": (
                None if blocklist_terms is None else json.dumps(blocklist_terms, ensure_ascii=False)
            ),
            "allowlist_boost": max(0, int(data.get("allowlist_boost", 15))),
            "source_ids_json": json.dumps(data.get("source_ids", [])),
            "frequency": data.get("frequency", "weekly"),
            "day_of_week": data.get("day_of_week", "mon"),
            "hour": int(data.get("hour", 8)),
            "minute": int(data.get("minute", 0)),
            "interval_hours": int(data.get("interval_hours", 12)),
            "min_score_override": data.get("min_score_override"),
            "min_language_score_override": data.get("min_language_score_override"),
            "employment_mode": (
                str(data.get("employment_mode", "prefer"))
                if str(data.get("employment_mode", "prefer")) in ("prefer", "strict")
                else "prefer"
            ),
            "min_cv_match": max(0, min(100, int(data.get("min_cv_match", 58)))),
            "max_results": int(data.get("max_results", 20)),
            "notify_telegram": int(bool(data.get("notify_telegram", False))),
            "notify_email": int(bool(data.get("notify_email", False))),
            "notification_json": json.dumps(notification, ensure_ascii=False),
            "secrets_json": json.dumps(existing_secrets),
            "updated_at": now,
        }
        if job_id:
            con.execute(
                """UPDATE search_jobs SET name=:name,enabled=:enabled,profile_id=:profile_id,inherit_location=:inherit_location,target_location=:target_location,location_terms_json=:location_terms_json,search_terms_json=:search_terms_json,allowlist_terms_json=:allowlist_terms_json,blocklist_terms_json=:blocklist_terms_json,allowlist_boost=:allowlist_boost,source_ids_json=:source_ids_json,frequency=:frequency,day_of_week=:day_of_week,hour=:hour,minute=:minute,interval_hours=:interval_hours,min_score_override=:min_score_override,min_language_score_override=:min_language_score_override,employment_mode=:employment_mode,min_cv_match=:min_cv_match,max_results=:max_results,notify_telegram=:notify_telegram,notify_email=:notify_email,notification_json=:notification_json,secrets_json=:secrets_json,updated_at=:updated_at WHERE id=:id AND user_id IS :user_id""",
                {**vals, "id": job_id},
            )
            return job_id
        cur = con.execute(
            """INSERT INTO search_jobs(user_id,name,enabled,profile_id,inherit_location,target_location,location_terms_json,search_terms_json,allowlist_terms_json,blocklist_terms_json,allowlist_boost,source_ids_json,frequency,day_of_week,hour,minute,interval_hours,min_score_override,min_language_score_override,employment_mode,min_cv_match,max_results,notify_telegram,notify_email,notification_json,secrets_json,created_at,updated_at)
                           VALUES(:user_id,:name,:enabled,:profile_id,:inherit_location,:target_location,:location_terms_json,:search_terms_json,:allowlist_terms_json,:blocklist_terms_json,:allowlist_boost,:source_ids_json,:frequency,:day_of_week,:hour,:minute,:interval_hours,:min_score_override,:min_language_score_override,:employment_mode,:min_cv_match,:max_results,:notify_telegram,:notify_email,:notification_json,:secrets_json,:created_at,:updated_at)""",
            {**vals, "created_at": now},
        )
        return int(cur.lastrowid)


def delete_search_job(job_id: int, user_id: int | None = None) -> None:
    ensure_search_job_schema(user_id)
    with connection() as con:
        con.execute("DELETE FROM search_jobs WHERE id=? AND user_id IS ?", (job_id, user_id))


def mark_search_job_seen(search_job_id: int, job_key: str) -> bool:
    now = _now()
    with connection() as con:
        row = con.execute(
            "SELECT first_seen FROM search_job_seen WHERE search_job_id=? AND job_key=?", (search_job_id, job_key)
        ).fetchone()
        if row:
            con.execute(
                "UPDATE search_job_seen SET last_seen=? WHERE search_job_id=? AND job_key=?",
                (now, search_job_id, job_key),
            )
            return False
        con.execute(
            "INSERT INTO search_job_seen(search_job_id,job_key,first_seen,last_seen) VALUES(?,?,?,?)",
            (search_job_id, job_key, now, now),
        )
        return True


def create_search_job_run(job_id: int) -> int:
    with connection() as con:
        return int(
            con.execute(
                "INSERT INTO search_job_runs(search_job_id,started_at,status) VALUES(?,?,'running')", (job_id, _now())
            ).lastrowid
        )


def acquire_search_job_lock(job_id: int, owner: str, lease_seconds: int = 900) -> bool:
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=max(60, lease_seconds))).isoformat()
    with connection() as con:
        con.execute("DELETE FROM search_job_locks WHERE expires_at <= ?", (now.isoformat(),))
        row = con.execute(
            """INSERT INTO search_job_locks(search_job_id,owner,expires_at) VALUES(?,?,?)
               ON CONFLICT(search_job_id) DO NOTHING RETURNING search_job_id""",
            (job_id, owner, expires_at),
        ).fetchone()
        return row is not None


def release_search_job_lock(job_id: int, owner: str) -> None:
    with connection() as con:
        con.execute("DELETE FROM search_job_locks WHERE search_job_id=? AND owner=?", (job_id, owner))


def finish_search_job_run(
    run_id: int,
    job_id: int,
    status: str,
    fetched: int = 0,
    matches: int = 0,
    provider_errors=None,
    channels=None,
    filter_counts=None,
    error: str = "",
) -> None:
    now = _now()
    with connection() as con:
        con.execute(
            """UPDATE search_job_runs SET finished_at=?,status=?,fetched=?,matches=?,provider_errors_json=?,notification_channels_json=?,filter_counts_json=?,error=? WHERE id=?""",
            (
                now,
                status,
                fetched,
                matches,
                json.dumps(provider_errors or []),
                json.dumps(channels or []),
                json.dumps(filter_counts or {}),
                error,
                run_id,
            ),
        )
        con.execute(
            "UPDATE search_jobs SET last_run_at=?,last_run_status=?,last_match_count=?,updated_at=? WHERE id=?",
            (now, status, matches, now, job_id),
        )


def list_search_job_runs(
    job_id: int | None = None, limit: int = 100, user_id: int | None = None
) -> list[dict[str, Any]]:
    ensure_search_job_schema(user_id)
    params: list[Any] = [user_id]
    where = "WHERE sj.user_id IS ?"
    if job_id:
        where += " AND r.search_job_id=?"
        params.append(job_id)
    params.append(limit)
    with connection() as con:
        rows = con.execute(
            f"""SELECT r.*,sj.name AS search_job_name FROM search_job_runs r JOIN search_jobs sj ON sj.id=r.search_job_id {where} ORDER BY r.id DESC LIMIT ?""",
            params,
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["provider_errors"] = json.loads(d.pop("provider_errors_json") or "[]")
        d["notification_channels"] = json.loads(d.pop("notification_channels_json") or "[]")
        d["filter_counts"] = json.loads(d.pop("filter_counts_json") or "{}")
        out.append(d)
    return out
