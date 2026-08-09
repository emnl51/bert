import json
from datetime import datetime, timezone
from typing import Any

from .db import connection

PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    target_location TEXT NOT NULL DEFAULT 'Berlin',
    location_terms_json TEXT NOT NULL DEFAULT '[]',
    min_score INTEGER NOT NULL DEFAULT 35,
    min_language_score INTEGER NOT NULL DEFAULT 40,
    language_weight INTEGER NOT NULL DEFAULT 35,
    current_german_level TEXT NOT NULL DEFAULT 'a2_b1',
    max_german_requirement TEXT NOT NULL DEFAULT 'b1',
    show_b2_stretch INTEGER NOT NULL DEFAULT 1,
    hide_german_heavy INTEGER NOT NULL DEFAULT 1,
    prefer_german_growth INTEGER NOT NULL DEFAULT 1,
    content_languages_json TEXT NOT NULL DEFAULT '["de","en","mixed"]',
    keywords_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_profiles_enabled ON search_profiles(enabled);

CREATE TABLE IF NOT EXISTS job_profile_scores (
    job_key TEXT NOT NULL,
    profile_id INTEGER NOT NULL,
    job_score INTEGER NOT NULL DEFAULT 0,
    language_score INTEGER NOT NULL DEFAULT 55,
    overall_score INTEGER NOT NULL DEFAULT 0,
    language_label TEXT NOT NULL DEFAULT 'unclear',
    reasons_json TEXT NOT NULL DEFAULT '[]',
    language_reasons_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(job_key, profile_id),
    FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_job_profile_scores_profile ON job_profile_scores(profile_id, overall_score DESC);
"""

WERKSTUDENT_KEYWORDS = {
    "search": {
        "werkstudent supply chain": 0,
        "working student supply chain": 0,
        "werkstudent procurement": 0,
        "working student procurement": 0,
        "werkstudent supply planning": 0,
        "working student supply planning": 0,
        "werkstudent order management": 0,
        "werkstudent operations": 0,
        "werkstudent logistik": 0,
        "working student logistics": 0,
    },
    "title": {
        "supply chain": 32,
        "supply planning": 32,
        "procurement": 30,
        "einkauf": 30,
        "order management": 28,
        "operations": 22,
        "logistics": 24,
        "material planning": 28,
    },
    "format": {
        "werkstudent": 34,
        "working student": 34,
        "student assistant": 26,
        "studentische aushilfe": 26,
        "teilzeit": 14,
        "part-time": 14,
        "part time": 14,
    },
    "skill": {
        "sap": 7,
        "s/4hana": 7,
        "power bi": 6,
        "excel": 4,
        "supplier": 5,
        "erp": 5,
        "production planning": 7,
        "international": 4,
        "customer": 4,
        "rfq": 5,
        "sourcing": 5,
        "inventory": 5,
    },
    "negative": {
        "software engineer": -35,
        "developer": -30,
        "nurse": -50,
        "pflege": -50,
        "driver": -35,
        "fahrer": -35,
        "restaurant": -35,
        "senior director": -20,
    },
}

FULLTIME_KEYWORDS = {
    "search": {
        "supply chain manager berlin": 0,
        "supply chain operations manager berlin": 0,
        "customer supply chain manager berlin": 0,
        "operations manager berlin": 0,
        "procurement manager berlin": 0,
        "strategic sourcing manager berlin": 0,
        "senior supply chain specialist berlin": 0,
    },
    "title": {
        "supply chain manager": 38,
        "supply chain operations": 36,
        "customer supply chain": 36,
        "operations manager": 32,
        "procurement manager": 34,
        "strategic sourcing": 32,
        "senior supply chain": 32,
        "supply planning manager": 32,
        "logistics manager": 26,
    },
    "format": {"full-time": 16, "full time": 16, "vollzeit": 16, "permanent": 10},
    "skill": {
        "sap": 9,
        "s/4hana": 9,
        "power bi": 7,
        "erp": 6,
        "supplier management": 8,
        "strategic sourcing": 8,
        "procurement": 8,
        "production planning": 7,
        "inventory": 6,
        "international": 6,
        "customer": 5,
        "leadership": 6,
        "stakeholder": 6,
        "incoterms": 5,
        "rfq": 5,
    },
    "negative": {
        "software engineer": -40,
        "developer": -35,
        "nurse": -50,
        "pflege": -50,
        "driver": -35,
        "fahrer": -35,
        "restaurant": -35,
        "internship": -18,
        "praktikum": -18,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_profile_schema() -> None:
    now = _now()
    with connection() as con:
        con.executescript(PROFILE_SCHEMA)
        columns = {row[1] for row in con.execute("PRAGMA table_info(search_profiles)").fetchall()}
        if "content_languages_json" not in columns:
            con.execute(
                'ALTER TABLE search_profiles ADD COLUMN content_languages_json TEXT NOT NULL DEFAULT \'["de","en","mixed"]\''
            )
        if con.execute("SELECT COUNT(*) FROM search_profiles").fetchone()[0] == 0:
            common_locations = json.dumps(
                [
                    "berlin",
                    "potsdam",
                    "hennigsdorf",
                    "ludwigsfelde",
                    "teltow",
                    "wildau",
                    "schönefeld",
                    "schoenefeld",
                    "oranienburg",
                    "brandenburg",
                ]
            )
            con.execute(
                """INSERT INTO search_profiles(name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,max_german_requirement,show_b2_stretch,hide_german_heavy,prefer_german_growth,keywords_json,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "Werkstudent / Part-time",
                    "werkstudent",
                    1,
                    1,
                    "Berlin",
                    common_locations,
                    35,
                    40,
                    35,
                    "a2_b1",
                    "b1",
                    1,
                    1,
                    1,
                    json.dumps(WERKSTUDENT_KEYWORDS),
                    now,
                    now,
                ),
            )
            con.execute(
                """INSERT INTO search_profiles(name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,max_german_requirement,show_b2_stretch,hide_german_heavy,prefer_german_growth,keywords_json,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "Full-time Supply Chain",
                    "fulltime",
                    1,
                    0,
                    "Berlin",
                    common_locations,
                    40,
                    35,
                    25,
                    "b1",
                    "b2",
                    1,
                    0,
                    1,
                    json.dumps(FULLTIME_KEYWORDS),
                    now,
                    now,
                ),
            )


def _row_to_profile(row) -> dict[str, Any]:
    p = dict(row)
    p["enabled"] = bool(p["enabled"])
    p["is_default"] = bool(p["is_default"])
    p["show_b2_stretch"] = bool(p["show_b2_stretch"])
    p["hide_german_heavy"] = bool(p["hide_german_heavy"])
    p["prefer_german_growth"] = bool(p["prefer_german_growth"])
    p["content_languages"] = json.loads(p.pop("content_languages_json") or "[]")
    p["location_terms"] = json.loads(p.pop("location_terms_json") or "[]")
    p["keywords"] = json.loads(p.pop("keywords_json") or "{}")
    return p


def list_profiles(enabled_only: bool = False) -> list[dict[str, Any]]:
    ensure_profile_schema()
    sql = "SELECT * FROM search_profiles"
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY is_default DESC,id"
    with connection() as con:
        rows = con.execute(sql).fetchall()
    return [_row_to_profile(r) for r in rows]


def get_profile(profile_id: int | None = None) -> dict[str, Any] | None:
    ensure_profile_schema()
    with connection() as con:
        if profile_id:
            row = con.execute("SELECT * FROM search_profiles WHERE id=?", (profile_id,)).fetchone()
        else:
            row = con.execute("SELECT * FROM search_profiles ORDER BY is_default DESC,id LIMIT 1").fetchone()
    return _row_to_profile(row) if row else None


def save_profile(data: dict[str, Any], profile_id: int | None = None) -> int:
    ensure_profile_schema()
    now = _now()
    fields = {
        "name": data.get("name", "Search Profile").strip(),
        "slug": data.get("slug", "profile").strip().lower().replace(" ", "-"),
        "enabled": int(bool(data.get("enabled", True))),
        "is_default": int(bool(data.get("is_default", False))),
        "target_location": data.get("target_location", "Berlin"),
        "location_terms_json": json.dumps(data.get("location_terms", []), ensure_ascii=False),
        "min_score": int(data.get("min_score", 35)),
        "min_language_score": int(data.get("min_language_score", 40)),
        "language_weight": int(data.get("language_weight", 35)),
        "current_german_level": data.get("current_german_level", "a2_b1"),
        "max_german_requirement": data.get("max_german_requirement", "b1"),
        "show_b2_stretch": int(bool(data.get("show_b2_stretch", True))),
        "hide_german_heavy": int(bool(data.get("hide_german_heavy", True))),
        "prefer_german_growth": int(bool(data.get("prefer_german_growth", True))),
        "content_languages_json": json.dumps(data.get("content_languages", ["de", "en", "mixed"])),
        "keywords_json": json.dumps(data.get("keywords", {}), ensure_ascii=False),
    }
    with connection() as con:
        if fields["is_default"]:
            con.execute("UPDATE search_profiles SET is_default=0")
        if profile_id:
            con.execute(
                """UPDATE search_profiles SET name=:name,slug=:slug,enabled=:enabled,is_default=:is_default,target_location=:target_location,location_terms_json=:location_terms_json,min_score=:min_score,min_language_score=:min_language_score,language_weight=:language_weight,current_german_level=:current_german_level,max_german_requirement=:max_german_requirement,show_b2_stretch=:show_b2_stretch,hide_german_heavy=:hide_german_heavy,prefer_german_growth=:prefer_german_growth,content_languages_json=:content_languages_json,keywords_json=:keywords_json,updated_at=:updated_at WHERE id=:id""",
                {**fields, "updated_at": now, "id": profile_id},
            )
            return profile_id
        cur = con.execute(
            """INSERT INTO search_profiles(name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,max_german_requirement,show_b2_stretch,hide_german_heavy,prefer_german_growth,content_languages_json,keywords_json,created_at,updated_at)
                           VALUES(:name,:slug,:enabled,:is_default,:target_location,:location_terms_json,:min_score,:min_language_score,:language_weight,:current_german_level,:max_german_requirement,:show_b2_stretch,:hide_german_heavy,:prefer_german_growth,:content_languages_json,:keywords_json,:created_at,:updated_at)""",
            {**fields, "created_at": now, "updated_at": now},
        )
        return int(cur.lastrowid)


def delete_profile(profile_id: int) -> None:
    ensure_profile_schema()
    with connection() as con:
        row = con.execute("SELECT is_default FROM search_profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return
        if row["is_default"]:
            raise ValueError("Default profile cannot be deleted")
        con.execute("DELETE FROM search_profiles WHERE id=?", (profile_id,))


def upsert_profile_score(job, profile_id: int) -> None:
    with connection() as con:
        con.execute(
            """INSERT INTO job_profile_scores(job_key,profile_id,job_score,language_score,overall_score,language_label,reasons_json,language_reasons_json,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(job_key,profile_id) DO UPDATE SET job_score=excluded.job_score,language_score=excluded.language_score,overall_score=excluded.overall_score,language_label=excluded.language_label,reasons_json=excluded.reasons_json,language_reasons_json=excluded.language_reasons_json,updated_at=excluded.updated_at""",
            (
                job.key,
                profile_id,
                job.score,
                job.language_score,
                job.overall_score,
                job.language_label,
                json.dumps(job.reasons, ensure_ascii=False),
                json.dumps(job.language_reasons, ensure_ascii=False),
                _now(),
            ),
        )


def profile_search_terms() -> list[str]:
    terms = []
    for p in list_profiles(enabled_only=True):
        terms.extend((p.get("keywords") or {}).get("search", {}).keys())
    return list(dict.fromkeys(terms))


def list_jobs_for_profile(
    profile_id: int,
    limit: int = 100,
    min_score: int = 0,
    decision: str = "active",
    language: str = "preferred",
    content_language: str = "profile",
) -> list[dict[str, Any]]:
    ensure_profile_schema()
    where = ["s.profile_id=?", "s.overall_score>=?"]
    params: [Any] = [profile_id, min_score]
    if decision == "active":
        where.append("j.decision!='skip'")
    elif decision in ("unreviewed", "apply", "maybe", "skip"):
        where.append("j.decision=?")
        params.append(decision)
    if language == "preferred":
        where.append("s.language_label!='german_heavy'")
    elif language in ("english_first", "german_growth", "stretch", "german_heavy", "unclear"):
        where.append("s.language_label=?")
        params.append(language)
    if content_language == "profile":
        profile = get_profile(profile_id)
        allowed = profile.get("content_languages", []) if profile else []
        if allowed:
            where.append(f"j.content_language IN ({','.join('?' for _ in allowed)})")
            params.extend(allowed)
    elif content_language in ("de", "en", "mixed", "unknown"):
        where.append("j.content_language=?")
        params.append(content_language)
    params.append(limit)
    with connection() as con:
        rows = con.execute(
            f"""SELECT j.job_key,j.source,j.title,j.company,j.location,j.url,j.created_at,j.first_seen,j.decision,j.decision_at,
                                   j.content_language,j.content_language_confidence,j.content_language_source,
                                   s.job_score AS score,s.language_score,s.overall_score,s.language_label,s.reasons_json,s.language_reasons_json,
                                   a.status AS application_status,a.applied_at
                            FROM job_profile_scores s JOIN jobs j ON j.job_key=s.job_key
                            LEFT JOIN applications a ON a.job_key=j.job_key
                            WHERE {" AND ".join(where)}
                            ORDER BY j.first_seen DESC,s.overall_score DESC LIMIT ?""",
            params,
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        item["language_reasons"] = json.loads(item.pop("language_reasons_json") or "[]")
        out.append(item)
    return out
