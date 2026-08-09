import json
from datetime import datetime, timedelta, timezone
from typing import Any
from .db import connection
from .secrets import encrypt_secret, decrypt_secret

SEARCH_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    profile_id INTEGER NOT NULL,
    target_location TEXT NOT NULL DEFAULT 'Berlin',
    location_terms_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    frequency TEXT NOT NULL DEFAULT 'weekly',
    day_of_week TEXT NOT NULL DEFAULT 'mon',
    hour INTEGER NOT NULL DEFAULT 8,
    minute INTEGER NOT NULL DEFAULT 0,
    interval_hours INTEGER NOT NULL DEFAULT 12,
    min_score_override INTEGER,
    min_language_score_override INTEGER,
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


def ensure_search_job_schema() -> None:
    from .profile_store import ensure_profile_schema, get_profile

    ensure_profile_schema()
    p = get_profile()
    with connection() as con:
        con.executescript(SEARCH_JOB_SCHEMA)
        if con.execute("SELECT COUNT(*) FROM search_jobs").fetchone()[0] == 0 and p:
            now = _now()
            con.execute(
                """INSERT INTO search_jobs(name,enabled,profile_id,target_location,location_terms_json,source_ids_json,frequency,day_of_week,hour,minute,interval_hours,max_results,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
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
    for k in ("enabled", "notify_telegram", "notify_email"):
        d[k] = bool(d[k])
    d["location_terms"] = json.loads(d.pop("location_terms_json") or "[]")
    d["source_ids"] = json.loads(d.pop("source_ids_json") or "[]")
    d["notification"] = json.loads(d.pop("notification_json") or "{}")
    enc = json.loads(d.pop("secrets_json") or "{}")
    d["secrets"] = {k: ("configured" if mask_secrets and v else decrypt_secret(v)) for k, v in enc.items()}
    return d


def list_search_jobs(mask_secrets: bool = True) -> list[dict[str, Any]]:
    ensure_search_job_schema()
    with connection() as con:
        rows = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj JOIN search_profiles sp ON sp.id=sj.profile_id ORDER BY sj.enabled DESC,sj.id"""
        ).fetchall()
    return [_decode(r, mask_secrets) for r in rows]


def get_search_job(job_id: int, mask_secrets: bool = False) -> dict[str, Any] | None:
    ensure_search_job_schema()
    with connection() as con:
        row = con.execute(
            """SELECT sj.*,sp.name AS profile_name FROM search_jobs sj JOIN search_profiles sp ON sp.id=sj.profile_id WHERE sj.id=?""",
            (job_id,),
        ).fetchone()
    return _decode(row, mask_secrets) if row else None


def save_search_job(data: dict[str, Any], job_id: int | None = None) -> int:
    ensure_search_job_schema()
    now = _now()
    notification = dict(data.get("notification") or {})
    supplied_secrets = dict(data.get("secrets") or {})
    with connection() as con:
        existing_secrets = {}
        if job_id:
            row = con.execute("SELECT secrets_json FROM search_jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValueError("Search job not found")
            existing_secrets = json.loads(row["secrets_json"] or "{}")
        for key, value in supplied_secrets.items():
            if key in SECRET_FIELDS and value and value != "configured":
                existing_secrets[key] = encrypt_secret(value)
        vals = {
            "name": str(data.get("name", "Search Job")).strip(),
            "enabled": int(bool(data.get("enabled", True))),
            "profile_id": int(data["profile_id"]),
            "target_location": str(data.get("target_location", "Berlin")),
            "location_terms_json": json.dumps(data.get("location_terms", []), ensure_ascii=False),
            "source_ids_json": json.dumps(data.get("source_ids", [])),
            "frequency": data.get("frequency", "weekly"),
            "day_of_week": data.get("day_of_week", "mon"),
            "hour": int(data.get("hour", 8)),
            "minute": int(data.get("minute", 0)),
            "interval_hours": int(data.get("interval_hours", 12)),
            "min_score_override": data.get("min_score_override"),
            "min_language_score_override": data.get("min_language_score_override"),
            "max_results": int(data.get("max_results", 20)),
            "notify_telegram": int(bool(data.get("notify_telegram", False))),
            "notify_email": int(bool(data.get("notify_email", False))),
            "notification_json": json.dumps(notification, ensure_ascii=False),
            "secrets_json": json.dumps(existing_secrets),
            "updated_at": now,
        }
        if job_id:
            con.execute(
                """UPDATE search_jobs SET name=:name,enabled=:enabled,profile_id=:profile_id,target_location=:target_location,location_terms_json=:location_terms_json,source_ids_json=:source_ids_json,frequency=:frequency,day_of_week=:day_of_week,hour=:hour,minute=:minute,interval_hours=:interval_hours,min_score_override=:min_score_override,min_language_score_override=:min_language_score_override,max_results=:max_results,notify_telegram=:notify_telegram,notify_email=:notify_email,notification_json=:notification_json,secrets_json=:secrets_json,updated_at=:updated_at WHERE id=:id""",
                {**vals, "id": job_id},
            )
            return job_id
        cur = con.execute(
            """INSERT INTO search_jobs(name,enabled,profile_id,target_location,location_terms_json,source_ids_json,frequency,day_of_week,hour,minute,interval_hours,min_score_override,min_language_score_override,max_results,notify_telegram,notify_email,notification_json,secrets_json,created_at,updated_at)
                           VALUES(:name,:enabled,:profile_id,:target_location,:location_terms_json,:source_ids_json,:frequency,:day_of_week,:hour,:minute,:interval_hours,:min_score_override,:min_language_score_override,:max_results,:notify_telegram,:notify_email,:notification_json,:secrets_json,:created_at,:updated_at)""",
            {**vals, "created_at": now},
        )
        return int(cur.lastrowid)


def delete_search_job(job_id: int) -> None:
    ensure_search_job_schema()
    with connection() as con:
        con.execute("DELETE FROM search_jobs WHERE id=?", (job_id,))


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
    error: str = "",
) -> None:
    now = _now()
    with connection() as con:
        con.execute(
            """UPDATE search_job_runs SET finished_at=?,status=?,fetched=?,matches=?,provider_errors_json=?,notification_channels_json=?,error=? WHERE id=?""",
            (
                now,
                status,
                fetched,
                matches,
                json.dumps(provider_errors or []),
                json.dumps(channels or []),
                error,
                run_id,
            ),
        )
        con.execute(
            "UPDATE search_jobs SET last_run_at=?,last_run_status=?,last_match_count=?,updated_at=? WHERE id=?",
            (now, status, matches, now, job_id),
        )


def list_search_job_runs(job_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    ensure_search_job_schema()
    params = []
    where = ""
    if job_id:
        where = "WHERE r.search_job_id=?"
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
        out.append(d)
    return out
