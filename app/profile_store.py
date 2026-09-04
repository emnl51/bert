import json
from datetime import datetime, timezone
from typing import Any

from .db import connection
from .employment_filter import profile_requires_confirmed_work_time
from .job_metadata import classify_job_metadata

PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    target_location TEXT NOT NULL DEFAULT 'Berlin',
    location_terms_json TEXT NOT NULL DEFAULT '[]',
    min_score INTEGER NOT NULL DEFAULT 35,
    min_language_score INTEGER NOT NULL DEFAULT 40,
    language_weight INTEGER NOT NULL DEFAULT 35,
    current_german_level TEXT NOT NULL DEFAULT 'a2_b1',
    current_english_level TEXT NOT NULL DEFAULT 'b1',
    max_german_requirement TEXT NOT NULL DEFAULT 'b1',
    preferred_weekly_hours INTEGER,
    availability TEXT NOT NULL DEFAULT 'any',
    role_level TEXT NOT NULL DEFAULT 'any',
    show_b2_stretch INTEGER NOT NULL DEFAULT 1,
    hide_german_heavy INTEGER NOT NULL DEFAULT 1,
    prefer_german_growth INTEGER NOT NULL DEFAULT 1,
    content_languages_json TEXT NOT NULL DEFAULT '["de","en","mixed"]',
    keywords_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, name),
    UNIQUE(user_id, slug),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_search_profiles_enabled ON search_profiles(enabled);

CREATE TABLE IF NOT EXISTS job_profile_scores (
    job_key TEXT NOT NULL,
    profile_id INTEGER NOT NULL,
    job_score INTEGER NOT NULL DEFAULT 0,
    language_score INTEGER NOT NULL DEFAULT 55,
    overall_score INTEGER NOT NULL DEFAULT 0,
    role_relevant INTEGER NOT NULL DEFAULT 0,
    match_tier TEXT NOT NULL DEFAULT 'excluded',
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
    "allowlist": {},
    "blocklist": {
        "software engineer": -100,
        "developer": -100,
        "nurse": -100,
        "pflege": -100,
        "driver": -100,
        "fahrer": -100,
        "restaurant": -100,
        "senior director": -100,
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
    "allowlist": {},
    "blocklist": {
        "software engineer": -100,
        "developer": -100,
        "nurse": -100,
        "pflege": -100,
        "driver": -100,
        "fahrer": -100,
        "restaurant": -100,
        "internship": -100,
        "praktikum": -100,
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backfill_role_relevance(con) -> None:
    """Re-evaluate legacy profile scores once when the structural role gate is added."""
    from .models import Job
    from .ranker import assess_role_relevance

    rows = con.execute(
        """SELECT s.job_key,s.profile_id,j.source,j.title,j.company,j.location,j.url,j.description,
                  j.created_at,j.remote,p.keywords_json,p.role_level
           FROM job_profile_scores s
           JOIN jobs j ON j.job_key=s.job_key
           JOIN search_profiles p ON p.id=s.profile_id"""
    ).fetchall()
    for row in rows:
        keywords = json.loads(row["keywords_json"] or "{}")
        job = Job(
            source=row["source"],
            external_id=row["job_key"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            url=row["url"],
            description=row["description"],
            created_at=row["created_at"],
            remote=bool(row["remote"]),
        )
        relevant = (
            row["source"] == "Manual" or assess_role_relevance(job, keywords, role_level=row["role_level"]).relevant
        )
        con.execute(
            "UPDATE job_profile_scores SET role_relevant=? WHERE job_key=? AND profile_id=?",
            (int(relevant), row["job_key"], row["profile_id"]),
        )


def _migrate_profile_ownership(con) -> None:
    columns = {row[1] for row in con.execute("PRAGMA table_info(search_profiles)").fetchall()}
    if not columns or "user_id" in columns:
        return
    con.execute("PRAGMA foreign_keys=OFF")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            """CREATE TABLE search_profiles_v18 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,name TEXT NOT NULL,slug TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,is_default INTEGER NOT NULL DEFAULT 0,
            target_location TEXT NOT NULL DEFAULT 'Berlin',location_terms_json TEXT NOT NULL DEFAULT '[]',
            min_score INTEGER NOT NULL DEFAULT 35,min_language_score INTEGER NOT NULL DEFAULT 40,
            language_weight INTEGER NOT NULL DEFAULT 35,current_german_level TEXT NOT NULL DEFAULT 'a2_b1',
            current_english_level TEXT NOT NULL DEFAULT 'b1',preferred_weekly_hours INTEGER,
            availability TEXT NOT NULL DEFAULT 'any',role_level TEXT NOT NULL DEFAULT 'any',
            max_german_requirement TEXT NOT NULL DEFAULT 'b1',show_b2_stretch INTEGER NOT NULL DEFAULT 1,
            hide_german_heavy INTEGER NOT NULL DEFAULT 1,prefer_german_growth INTEGER NOT NULL DEFAULT 1,
            content_languages_json TEXT NOT NULL DEFAULT '[\"de\",\"en\",\"mixed\"]',
            keywords_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            UNIQUE(user_id,name),UNIQUE(user_id,slug),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)"""
        )
        con.execute(
            """INSERT INTO search_profiles_v18
            (id,user_id,name,slug,enabled,is_default,target_location,location_terms_json,min_score,
             min_language_score,language_weight,current_german_level,current_english_level,
             preferred_weekly_hours,availability,role_level,max_german_requirement,
             show_b2_stretch,hide_german_heavy,prefer_german_growth,content_languages_json,
             keywords_json,created_at,updated_at)
            SELECT id,NULL,name,slug,enabled,is_default,target_location,location_terms_json,min_score,
             min_language_score,language_weight,current_german_level,'b1',NULL,'any','any',max_german_requirement,
             show_b2_stretch,hide_german_heavy,prefer_german_growth,
             COALESCE(content_languages_json,'[\"de\",\"en\",\"mixed\"]'),keywords_json,created_at,updated_at
            FROM search_profiles"""
        )
        con.execute("DROP TABLE search_profiles")
        con.execute("ALTER TABLE search_profiles_v18 RENAME TO search_profiles")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.execute("PRAGMA foreign_keys=ON")


def ensure_profile_schema(user_id: int | None = None) -> None:
    from .user_store import ensure_user_schema

    ensure_user_schema()
    now = _now()
    with connection() as con:
        con.executescript(PROFILE_SCHEMA)
        _migrate_profile_ownership(con)
        con.execute("CREATE INDEX IF NOT EXISTS idx_search_profiles_enabled ON search_profiles(user_id,enabled)")
        columns = {row[1] for row in con.execute("PRAGMA table_info(search_profiles)").fetchall()}
        if "content_languages_json" not in columns:
            con.execute(
                'ALTER TABLE search_profiles ADD COLUMN content_languages_json TEXT NOT NULL DEFAULT \'["de","en","mixed"]\''
            )
        english_column_added = "current_english_level" not in columns
        if english_column_added:
            con.execute("ALTER TABLE search_profiles ADD COLUMN current_english_level TEXT NOT NULL DEFAULT 'b1'")
        if "preferred_weekly_hours" not in columns:
            con.execute("ALTER TABLE search_profiles ADD COLUMN preferred_weekly_hours INTEGER")
        if "availability" not in columns:
            con.execute("ALTER TABLE search_profiles ADD COLUMN availability TEXT NOT NULL DEFAULT 'any'")
        if "role_level" not in columns:
            con.execute("ALTER TABLE search_profiles ADD COLUMN role_level TEXT NOT NULL DEFAULT 'any'")
        if english_column_added:
            for row in con.execute("SELECT id,keywords_json FROM search_profiles").fetchall():
                keywords = json.loads(row["keywords_json"] or "{}")
                legacy = next(
                    (
                        term.removeprefix("english_")
                        for term in (keywords.get("language") or {})
                        if term.startswith("english_")
                    ),
                    None,
                )
                if legacy in {"a2", "b1", "b2", "c1", "c2"}:
                    con.execute("UPDATE search_profiles SET current_english_level=? WHERE id=?", (legacy, row["id"]))
        score_columns = {row[1] for row in con.execute("PRAGMA table_info(job_profile_scores)").fetchall()}
        if "role_relevant" not in score_columns:
            con.execute("ALTER TABLE job_profile_scores ADD COLUMN role_relevant INTEGER NOT NULL DEFAULT 0")
            _backfill_role_relevance(con)
        if "match_tier" not in score_columns:
            con.execute("ALTER TABLE job_profile_scores ADD COLUMN match_tier TEXT NOT NULL DEFAULT 'excluded'")
            con.execute(
                """UPDATE job_profile_scores SET match_tier=CASE
                   WHEN role_relevant=0 THEN 'excluded'
                   WHEN overall_score>=75 THEN 'strong'
                   ELSE 'match' END"""
            )
        for row in con.execute("SELECT id,keywords_json FROM search_profiles").fetchall():
            keywords = json.loads(row["keywords_json"] or "{}")
            changed = False
            if "allowlist" not in keywords:
                keywords["allowlist"] = {}
                changed = True
            if "blocklist" not in keywords:
                # Existing negative rules historically reduced the score. Treating the
                # same terms as hard exclusions preserves the user's intent while the
                # old penalties remain readable for backwards compatibility.
                keywords["blocklist"] = {term: -100 for term in (keywords.get("negative") or {})}
                changed = True
            if changed:
                con.execute(
                    "UPDATE search_profiles SET keywords_json=?,updated_at=? WHERE id=?",
                    (json.dumps(keywords, ensure_ascii=False), now, row["id"]),
                )
        # Preserve legacy administrator defaults, but leave registered accounts
        # empty so they never inherit sample or another owner's workspace data.
        if (
            user_id is None
            and con.execute("SELECT COUNT(*) FROM search_profiles WHERE user_id IS NULL").fetchone()[0] == 0
        ):
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
                """INSERT INTO search_profiles(user_id,name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,max_german_requirement,show_b2_stretch,hide_german_heavy,prefer_german_growth,keywords_json,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
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
                """INSERT INTO search_profiles(user_id,name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,max_german_requirement,show_b2_stretch,hide_german_heavy,prefer_german_growth,keywords_json,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
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
    p["preferred_weekly_hours"] = (
        int(p["preferred_weekly_hours"]) if p.get("preferred_weekly_hours") is not None else None
    )
    p["content_languages"] = json.loads(p.pop("content_languages_json") or "[]")
    p["location_terms"] = json.loads(p.pop("location_terms_json") or "[]")
    p["keywords"] = json.loads(p.pop("keywords_json") or "{}")
    p["keywords"].setdefault("allowlist", {})
    p["keywords"].setdefault("blocklist", {})
    return p


def list_profiles(enabled_only: bool = False, user_id: int | None = None) -> list[dict[str, Any]]:
    ensure_profile_schema(user_id)
    sql = "SELECT * FROM search_profiles WHERE user_id IS ?"
    params: list[Any] = [user_id]
    if enabled_only:
        sql += " AND enabled=1"
    sql += " ORDER BY is_default DESC,id"
    with connection() as con:
        rows = con.execute(sql, params).fetchall()
    return [_row_to_profile(r) for r in rows]


def get_profile(profile_id: int | None = None, user_id: int | None = None) -> dict[str, Any] | None:
    ensure_profile_schema(user_id)
    with connection() as con:
        if profile_id:
            row = con.execute(
                "SELECT * FROM search_profiles WHERE id=? AND user_id IS ?", (profile_id, user_id)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM search_profiles WHERE user_id IS ? ORDER BY is_default DESC,id LIMIT 1", (user_id,)
            ).fetchone()
    return _row_to_profile(row) if row else None


def save_profile(data: dict[str, Any], profile_id: int | None = None, user_id: int | None = None) -> int:
    ensure_profile_schema(user_id)
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
        "current_english_level": data.get("current_english_level", "b1"),
        "max_german_requirement": data.get("max_german_requirement", "b1"),
        "preferred_weekly_hours": data.get("preferred_weekly_hours"),
        "availability": data.get("availability", "any"),
        "role_level": data.get("role_level", "any"),
        "show_b2_stretch": int(bool(data.get("show_b2_stretch", True))),
        "hide_german_heavy": int(bool(data.get("hide_german_heavy", True))),
        "prefer_german_growth": int(bool(data.get("prefer_german_growth", True))),
        "content_languages_json": json.dumps(data.get("content_languages", ["de", "en", "mixed"])),
        "keywords_json": json.dumps(data.get("keywords", {}), ensure_ascii=False),
    }
    with connection() as con:
        if fields["is_default"]:
            con.execute("UPDATE search_profiles SET is_default=0 WHERE user_id IS ?", (user_id,))
        if profile_id:
            con.execute(
                """UPDATE search_profiles SET name=:name,slug=:slug,enabled=:enabled,is_default=:is_default,target_location=:target_location,location_terms_json=:location_terms_json,min_score=:min_score,min_language_score=:min_language_score,language_weight=:language_weight,current_german_level=:current_german_level,current_english_level=:current_english_level,max_german_requirement=:max_german_requirement,preferred_weekly_hours=:preferred_weekly_hours,availability=:availability,role_level=:role_level,show_b2_stretch=:show_b2_stretch,hide_german_heavy=:hide_german_heavy,prefer_german_growth=:prefer_german_growth,content_languages_json=:content_languages_json,keywords_json=:keywords_json,updated_at=:updated_at WHERE id=:id AND user_id IS :user_id""",
                {**fields, "updated_at": now, "id": profile_id, "user_id": user_id},
            )
            if con.execute("SELECT changes()").fetchone()[0] == 0:
                raise ValueError("Profile not found")
            return profile_id
        cur = con.execute(
            """INSERT INTO search_profiles(user_id,name,slug,enabled,is_default,target_location,location_terms_json,min_score,min_language_score,language_weight,current_german_level,current_english_level,max_german_requirement,preferred_weekly_hours,availability,role_level,show_b2_stretch,hide_german_heavy,prefer_german_growth,content_languages_json,keywords_json,created_at,updated_at)
                           VALUES(:user_id,:name,:slug,:enabled,:is_default,:target_location,:location_terms_json,:min_score,:min_language_score,:language_weight,:current_german_level,:current_english_level,:max_german_requirement,:preferred_weekly_hours,:availability,:role_level,:show_b2_stretch,:hide_german_heavy,:prefer_german_growth,:content_languages_json,:keywords_json,:created_at,:updated_at)""",
            {**fields, "user_id": user_id, "created_at": now, "updated_at": now},
        )
        return int(cur.lastrowid)


def delete_profile(profile_id: int, user_id: int | None = None) -> None:
    ensure_profile_schema(user_id)
    with connection() as con:
        row = con.execute(
            "SELECT is_default FROM search_profiles WHERE id=? AND user_id IS ?", (profile_id, user_id)
        ).fetchone()
        if not row:
            return
        if row["is_default"]:
            raise ValueError("Default profile cannot be deleted")
        has_search_jobs = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='search_jobs'"
        ).fetchone()
        linked = (
            con.execute(
                "SELECT name FROM search_jobs WHERE profile_id=? AND user_id IS ? ORDER BY name",
                (profile_id, user_id),
            ).fetchall()
            if has_search_jobs
            else []
        )
        if linked:
            names = ", ".join(item["name"] for item in linked)
            raise ValueError(f"Profile is used by search jobs: {names}. Reassign or delete them first.")
        con.execute("DELETE FROM search_profiles WHERE id=? AND user_id IS ?", (profile_id, user_id))


def upsert_profile_score(
    job,
    profile_id: int,
    role_relevant: bool | None = None,
    match_tier: str | None = None,
) -> None:
    if role_relevant is None:
        role_relevant = bool(getattr(job, "role_relevant", True))
    if match_tier is None:
        match_tier = str(getattr(job, "match_tier", "match" if role_relevant else "excluded"))
    if match_tier not in ("strong", "match", "stretch", "excluded"):
        match_tier = "match" if role_relevant else "excluded"
    with connection() as con:
        con.execute(
            """INSERT INTO job_profile_scores(job_key,profile_id,job_score,language_score,overall_score,role_relevant,match_tier,language_label,reasons_json,language_reasons_json,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_key,profile_id) DO UPDATE SET job_score=excluded.job_score,language_score=excluded.language_score,overall_score=excluded.overall_score,role_relevant=excluded.role_relevant,match_tier=excluded.match_tier,language_label=excluded.language_label,reasons_json=excluded.reasons_json,language_reasons_json=excluded.language_reasons_json,updated_at=excluded.updated_at""",
            (
                job.key,
                profile_id,
                job.score,
                job.language_score,
                job.overall_score,
                int(role_relevant),
                match_tier,
                job.language_label,
                json.dumps(job.reasons, ensure_ascii=False),
                json.dumps(job.language_reasons, ensure_ascii=False),
                _now(),
            ),
        )


def profile_search_terms(user_id: int | None = None) -> list[str]:
    terms = []
    for p in list_profiles(enabled_only=True, user_id=user_id):
        terms.extend((p.get("keywords") or {}).get("search", {}).keys())
    return list(dict.fromkeys(terms))


def list_jobs_for_profile(
    profile_id: int,
    limit: int = 100,
    min_score: int = 0,
    decision: str = "active",
    language: str = "preferred",
    content_language: str = "profile",
    tier: str = "all",
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    ensure_profile_schema(user_id)
    profile = get_profile(profile_id, user_id=user_id)
    if not profile:
        return []
    owner_key = "admin" if user_id is None else f"user:{int(user_id)}"
    where = ["s.profile_id=?", "s.role_relevant=1", "s.match_tier!='excluded'", "s.overall_score>=?"]
    params: list[Any] = [profile_id, min_score]
    if decision == "active":
        where.append("COALESCE(js.decision,'unreviewed')!='skip'")
    elif decision in ("unreviewed", "apply", "maybe", "skip"):
        where.append("COALESCE(js.decision,'unreviewed')=?")
        params.append(decision)
    if language == "preferred":
        where.append("s.language_label!='german_heavy'")
    elif language in ("english_first", "german_growth", "stretch", "german_heavy", "unclear"):
        where.append("s.language_label=?")
        params.append(language)
    if content_language == "profile":
        allowed = profile.get("content_languages", []) if profile else []
        if allowed:
            where.append(f"j.content_language IN ({','.join('?' for _ in allowed)})")
            params.extend(allowed)
    elif content_language in ("de", "en", "mixed", "unknown"):
        where.append("j.content_language=?")
        params.append(content_language)
    if tier in ("strong", "match", "stretch"):
        where.append("s.match_tier=?")
        params.append(tier)
    params = [owner_key, owner_key, *params, limit]
    with connection() as con:
        rows = con.execute(
            f"""SELECT j.job_key,j.source,j.title,j.company,j.location,j.url,j.description,j.created_at,j.first_seen,j.remote,
                                   COALESCE(js.decision,'unreviewed') AS decision,js.decision_at,
                                   j.content_language,j.content_language_confidence,j.content_language_source,
                                   s.job_score AS score,s.language_score,s.overall_score,s.role_relevant,s.match_tier,s.language_label,s.reasons_json,s.language_reasons_json,
                                   a.status AS application_status,a.applied_at
                            FROM job_profile_scores s JOIN jobs j ON j.job_key=s.job_key
                            LEFT JOIN user_job_state js ON js.owner_key=? AND js.job_key=j.job_key
                            LEFT JOIN applications a ON a.owner_key=? AND a.job_key=j.job_key
                            WHERE {" AND ".join(where)}
                            ORDER BY j.first_seen DESC,s.overall_score DESC LIMIT ?""",
            params,
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        item["language_reasons"] = json.loads(item.pop("language_reasons_json") or "[]")
        item.update(classify_job_metadata(item))
        if profile_requires_confirmed_work_time(profile) and item["employment_type"] == "unknown":
            continue
        item.pop("description", None)
        item["remote"] = bool(item["remote"])
        item["role_relevant"] = bool(item["role_relevant"])
        out.append(item)
    return out


def get_job_for_profile(job_key: str, profile_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    """Return one complete job only when it belongs to the user's search profile."""
    ensure_profile_schema(user_id)
    profile = get_profile(profile_id, user_id=user_id)
    if not profile:
        return None
    owner_key = "admin" if user_id is None else f"user:{int(user_id)}"
    with connection() as con:
        row = con.execute(
            """SELECT j.job_key,j.source,j.title,j.company,j.location,j.url,j.description,j.created_at,
                              j.first_seen,j.remote,j.content_language,j.content_language_confidence,
                              j.content_language_source,COALESCE(js.decision,'unreviewed') AS decision,
                              js.decision_at,s.job_score AS score,s.language_score,s.overall_score,
                              s.role_relevant,s.match_tier,s.language_label,s.reasons_json,s.language_reasons_json,
                              a.status AS application_status,a.applied_at
                       FROM job_profile_scores s
                       JOIN jobs j ON j.job_key=s.job_key
                       LEFT JOIN user_job_state js ON js.owner_key=? AND js.job_key=j.job_key
                       LEFT JOIN applications a ON a.owner_key=? AND a.job_key=j.job_key
                       WHERE s.profile_id=? AND s.role_relevant=1 AND s.match_tier!='excluded' AND j.job_key=?""",
            (owner_key, owner_key, profile_id, job_key),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
    item["language_reasons"] = json.loads(item.pop("language_reasons_json") or "[]")
    item.update(classify_job_metadata(item))
    if profile_requires_confirmed_work_time(profile) and item["employment_type"] == "unknown":
        return None
    item["remote"] = bool(item["remote"])
    item["role_relevant"] = bool(item["role_relevant"])
    return item
