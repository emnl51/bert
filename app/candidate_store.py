import json
from datetime import datetime, timezone
from typing import Any
from .db import connection
from .secrets import encrypt_secret, decrypt_secret

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_profiles (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER,
 name TEXT NOT NULL,
 headline TEXT NOT NULL DEFAULT '',
 cv_text TEXT NOT NULL DEFAULT '',
 skills_json TEXT NOT NULL DEFAULT '[]',
 languages_json TEXT NOT NULL DEFAULT '{}',
 target_roles_json TEXT NOT NULL DEFAULT '[]',
 notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(user_id,name),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS search_job_candidates (
 search_job_id INTEGER PRIMARY KEY,
 candidate_profile_id INTEGER NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1,
 FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE,
 FOREIGN KEY(candidate_profile_id) REFERENCES candidate_profiles(id) ON DELETE RESTRICT
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _migrate_candidate_ownership(con):
    columns = {row[1] for row in con.execute("PRAGMA table_info(candidate_profiles)").fetchall()}
    if not columns or "user_id" in columns:
        return
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """CREATE TABLE candidate_profiles_v18 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,name TEXT NOT NULL,
            headline TEXT NOT NULL DEFAULT '',cv_text TEXT NOT NULL DEFAULT '',
            skills_json TEXT NOT NULL DEFAULT '[]',languages_json TEXT NOT NULL DEFAULT '{}',
            target_roles_json TEXT NOT NULL DEFAULT '[]',notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(user_id,name),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)"""
        )
        con.execute(
            """INSERT INTO candidate_profiles_v18
            (id,user_id,name,headline,cv_text,skills_json,languages_json,target_roles_json,notes,created_at,updated_at)
            SELECT id,NULL,name,headline,cv_text,skills_json,languages_json,target_roles_json,notes,created_at,updated_at
            FROM candidate_profiles"""
        )
        con.execute("DROP TABLE candidate_profiles")
        con.execute("ALTER TABLE candidate_profiles_v18 RENAME TO candidate_profiles")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


def ensure_candidate_schema():
    from .user_store import ensure_user_schema

    ensure_user_schema()
    with connection() as con:
        con.executescript(SCHEMA)
        _migrate_candidate_ownership(con)


def _decrypt_cv(value: str) -> str:
    if not value:
        return ""
    try:
        return decrypt_secret(value)
    except Exception:
        return value


def _decode(row):
    d = dict(row)
    d["cv_text"] = _decrypt_cv(d.get("cv_text", ""))
    d["skills"] = json.loads(d.pop("skills_json") or "[]")
    d["languages"] = json.loads(d.pop("languages_json") or "{}")
    d["target_roles"] = json.loads(d.pop("target_roles_json") or "[]")
    return d


def list_candidates(user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        rows = con.execute("SELECT * FROM candidate_profiles WHERE user_id IS ? ORDER BY name", (user_id,)).fetchall()
    return [_decode(r) for r in rows]


def get_candidate(candidate_id: int, user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        row = con.execute(
            "SELECT * FROM candidate_profiles WHERE id=? AND user_id IS ?", (candidate_id, user_id)
        ).fetchone()
    return _decode(row) if row else None


def save_candidate(data: dict[str, Any], candidate_id: int | None = None, user_id=None):
    ensure_candidate_schema()
    now = _now()
    vals = {
        "name": data.get("name", "Candidate").strip(),
        "user_id": user_id,
        "headline": data.get("headline", "").strip(),
        "cv_text": encrypt_secret(data.get("cv_text", "")) if data.get("cv_text", "") else "",
        "skills_json": json.dumps(data.get("skills", []), ensure_ascii=False),
        "languages_json": json.dumps(data.get("languages", {}), ensure_ascii=False),
        "target_roles_json": json.dumps(data.get("target_roles", []), ensure_ascii=False),
        "notes": data.get("notes", ""),
        "updated_at": now,
    }
    with connection() as con:
        if candidate_id:
            con.execute(
                "UPDATE candidate_profiles SET name=:name,headline=:headline,cv_text=:cv_text,skills_json=:skills_json,languages_json=:languages_json,target_roles_json=:target_roles_json,notes=:notes,updated_at=:updated_at WHERE id=:id AND user_id IS :user_id",
                {**vals, "id": candidate_id},
            )
            return candidate_id
        cur = con.execute(
            "INSERT INTO candidate_profiles(user_id,name,headline,cv_text,skills_json,languages_json,target_roles_json,notes,created_at,updated_at) VALUES(:user_id,:name,:headline,:cv_text,:skills_json,:languages_json,:target_roles_json,:notes,:created_at,:updated_at)",
            {**vals, "created_at": now},
        )
        return int(cur.lastrowid)


def delete_candidate(candidate_id: int, user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        used = con.execute(
            """SELECT COUNT(*) FROM search_job_candidates m JOIN candidate_profiles c
               ON c.id=m.candidate_profile_id WHERE c.id=? AND c.user_id IS ?""",
            (candidate_id, user_id),
        ).fetchone()[0]
        if used:
            raise ValueError("Candidate profile is assigned to a Search Job")
        con.execute("DELETE FROM candidate_profiles WHERE id=? AND user_id IS ?", (candidate_id, user_id))


def assign_candidate(search_job_id: int, candidate_profile_id: int | None, enabled: bool = True, user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        search_job = con.execute(
            "SELECT id FROM search_jobs WHERE id=? AND user_id IS ?", (search_job_id, user_id)
        ).fetchone()
        if not search_job:
            raise ValueError("Search job not found")
        if not candidate_profile_id:
            con.execute("DELETE FROM search_job_candidates WHERE search_job_id=?", (search_job_id,))
            return
        candidate = con.execute(
            "SELECT id FROM candidate_profiles WHERE id=? AND user_id IS ?", (candidate_profile_id, user_id)
        ).fetchone()
        if not candidate:
            raise ValueError("Candidate profile not found")
        con.execute(
            "INSERT INTO search_job_candidates(search_job_id,candidate_profile_id,enabled) VALUES(?,?,?) ON CONFLICT(search_job_id) DO UPDATE SET candidate_profile_id=excluded.candidate_profile_id,enabled=excluded.enabled",
            (search_job_id, candidate_profile_id, int(enabled)),
        )


def candidate_for_search_job(search_job_id: int, user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        row = con.execute(
            """SELECT c.* FROM search_job_candidates m JOIN candidate_profiles c ON c.id=m.candidate_profile_id
               JOIN search_jobs sj ON sj.id=m.search_job_id
               WHERE m.search_job_id=? AND m.enabled=1 AND c.user_id IS ? AND sj.user_id IS ?""",
            (search_job_id, user_id, user_id),
        ).fetchone()
    return _decode(row) if row else None


def mapping_for_jobs(user_id=None):
    ensure_candidate_schema()
    with connection() as con:
        rows = con.execute(
            """SELECT m.search_job_id,m.candidate_profile_id,m.enabled FROM search_job_candidates m
               JOIN search_jobs sj ON sj.id=m.search_job_id WHERE sj.user_id IS ?""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]
