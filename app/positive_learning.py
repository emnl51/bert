import re
from datetime import datetime, timezone
from .db import connection

POSITIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS positive_rules (
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL DEFAULT 1, scope TEXT NOT NULL, term TEXT NOT NULL,
 weight INTEGER NOT NULL DEFAULT 4, evidence_count INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 1,
 strongest_event TEXT NOT NULL DEFAULT 'suitable', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positive_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT NOT NULL, profile_id INTEGER NOT NULL DEFAULT 1,
 event_type TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_positive_rules_profile ON positive_rules(profile_id,enabled);
CREATE INDEX IF NOT EXISTS idx_positive_events_profile ON positive_events(profile_id,job_key);
"""
EVENT_STRENGTH = {"suitable": 4, "applied": 5, "interview": 9, "offer": 14}
EVENT_RANK = {"suitable": 1, "applied": 2, "interview": 3, "offer": 4}
STOPWORDS = {
    "werkstudent",
    "working",
    "student",
    "studentin",
    "studentische",
    "m",
    "w",
    "d",
    "f",
    "x",
    "and",
    "und",
    "the",
    "for",
    "für",
    "im",
    "in",
    "of",
    "at",
    "bei",
    "part",
    "time",
    "teilzeit",
    "intern",
    "internship",
    "praktikum",
    "praktikant",
    "praktikantin",
    "junior",
    "senior",
    "manager",
}
SKILL_TERMS = (
    "supply chain",
    "supply planning",
    "demand planning",
    "material planning",
    "procurement",
    "einkauf",
    "purchasing",
    "order management",
    "operations",
    "logistics",
    "logistik",
    "strategic sourcing",
    "sourcing",
    "supplier",
    "lieferant",
    "sap",
    "s/4hana",
    "power bi",
    "excel",
    "erp",
    "inventory",
    "bestand",
    "production planning",
    "produktionsplanung",
    "international",
    "customer",
    "kunde",
    "material",
    "rfq",
    "incoterms",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalise(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-ZäöüÄÖÜß0-9+#./ -]+", " ", text or "").lower()).strip()


def _table_exists(con, table_name):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone())


def ensure_positive_schema():
    from .profile_store import ensure_profile_schema

    ensure_profile_schema()
    with connection() as con:
        con.executescript(POSITIVE_SCHEMA)
        cols = {r[1] for r in con.execute("PRAGMA table_info(positive_rules)").fetchall()}
        if "profile_id" not in cols:
            con.execute("ALTER TABLE positive_rules ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1")
        cols = {r[1] for r in con.execute("PRAGMA table_info(positive_events)").fetchall()}
        if "profile_id" not in cols:
            con.execute("ALTER TABLE positive_events ADD COLUMN profile_id INTEGER NOT NULL DEFAULT 1")
        ddl = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='positive_rules'").fetchone()
        if ddl and "UNIQUE(scope, term)" in (ddl["sql"] or ""):
            con.execute("ALTER TABLE positive_rules RENAME TO positive_rules_old_v9")
            con.execute(
                """CREATE TABLE positive_rules (id INTEGER PRIMARY KEY AUTOINCREMENT,profile_id INTEGER NOT NULL DEFAULT 1,scope TEXT NOT NULL,term TEXT NOT NULL,weight INTEGER NOT NULL DEFAULT 4,evidence_count INTEGER NOT NULL DEFAULT 1,enabled INTEGER NOT NULL DEFAULT 1,strongest_event TEXT NOT NULL DEFAULT 'suitable',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(profile_id,scope,term))"""
            )
            con.execute(
                """INSERT INTO positive_rules(id,profile_id,scope,term,weight,evidence_count,enabled,strongest_event,created_at,updated_at) SELECT id,COALESCE(profile_id,1),scope,term,weight,evidence_count,enabled,strongest_event,created_at,updated_at FROM positive_rules_old_v9"""
            )
            con.execute("DROP TABLE positive_rules_old_v9")
        ddl = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='positive_events'").fetchone()
        if ddl and "UNIQUE(job_key, event_type)" in (ddl["sql"] or ""):
            con.execute("ALTER TABLE positive_events RENAME TO positive_events_old_v9")
            con.execute(
                """CREATE TABLE positive_events (id INTEGER PRIMARY KEY AUTOINCREMENT,job_key TEXT NOT NULL,profile_id INTEGER NOT NULL DEFAULT 1,event_type TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(job_key,profile_id,event_type),FOREIGN KEY(job_key) REFERENCES jobs(job_key) ON DELETE CASCADE)"""
            )
            con.execute(
                """INSERT INTO positive_events(id,job_key,profile_id,event_type,created_at) SELECT id,job_key,COALESCE(profile_id,1),event_type,created_at FROM positive_events_old_v9"""
            )
            con.execute("DROP TABLE positive_events_old_v9")
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_positive_rule_profile_scope_term ON positive_rules(profile_id,scope,term)"
        )
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_positive_event_profile ON positive_events(job_key,profile_id,event_type)"
        )


def _role_terms(title):
    words = [w for w in _normalise(title).split() if len(w) >= 3 and w not in STOPWORDS]
    out = []
    if len(words) >= 2:
        out.append(" ".join(words[:2]))
    if words:
        out.append(words[0])
    return list(dict.fromkeys(t for t in out if len(t) >= 4))[:2]


def _extract_positive_rules(job, language_label, event_type):
    base = EVENT_STRENGTH[event_type]
    rules = [{"scope": "title", "term": t, "weight": base} for t in _role_terms(job.get("title", ""))]
    text = _normalise(f"{job.get('title', '')} {job.get('description', '')}")
    for term in [t for t in SKILL_TERMS if t in text][:4]:
        rules.append({"scope": "description", "term": term, "weight": max(2, base - 1)})
    if language_label in ("english_first", "german_growth"):
        rules.append({"scope": "language", "term": language_label, "weight": max(3, base)})
    if event_type in ("interview", "offer") and _normalise(job.get("company", "")):
        rules.append({"scope": "company", "term": _normalise(job.get("company", "")), "weight": base})
    return rules[:8]


def _upsert(con, profile_id, rule, event_type):
    row = con.execute(
        "SELECT id,evidence_count,weight,strongest_event FROM positive_rules WHERE profile_id=? AND scope=? AND term=?",
        (profile_id, rule["scope"], rule["term"]),
    ).fetchone()
    now = _now()
    if row:
        ev = int(row["evidence_count"]) + 1
        strongest = (
            row["strongest_event"]
            if EVENT_RANK.get(row["strongest_event"], 0) >= EVENT_RANK[event_type]
            else event_type
        )
        target = max(int(row["weight"]), int(rule["weight"])) + (1 if ev in (2, 4, 7, 12) else 0)
        weight = min(30, target)
        con.execute(
            "UPDATE positive_rules SET evidence_count=?,weight=?,enabled=1,strongest_event=?,updated_at=? WHERE id=?",
            (ev, weight, strongest, now, row["id"]),
        )
        return int(row["id"])
    cur = con.execute(
        "INSERT INTO positive_rules(profile_id,scope,term,weight,evidence_count,enabled,strongest_event,created_at,updated_at) VALUES(?,?,?,?,1,1,?,?,?)",
        (profile_id, rule["scope"], rule["term"], int(rule["weight"]), event_type, now, now),
    )
    return int(cur.lastrowid)


def record_positive_event(job_key, event_type, profile_id=1):
    if event_type not in EVENT_STRENGTH:
        raise ValueError("Invalid positive event")
    ensure_positive_schema()
    with connection() as con:
        job = con.execute("SELECT * FROM jobs WHERE job_key=?", (job_key,)).fetchone()
        if not job:
            raise ValueError("Job not found")
        if con.execute(
            "SELECT id FROM positive_events WHERE job_key=? AND profile_id=? AND event_type=?",
            (job_key, profile_id, event_type),
        ).fetchone():
            return {
                "job_key": job_key,
                "profile_id": profile_id,
                "event_type": event_type,
                "created": False,
                "positive_rule_ids": [],
            }
        lang = (
            con.execute(
                "SELECT language_label FROM job_profile_scores WHERE job_key=? AND profile_id=?", (job_key, profile_id)
            ).fetchone()
            if _table_exists(con, "job_profile_scores")
            else None
        )
        if not lang and _table_exists(con, "job_language"):
            lang = con.execute("SELECT language_label FROM job_language WHERE job_key=?", (job_key,)).fetchone()
        label = lang["language_label"] if lang else "unclear"
        ids = [_upsert(con, profile_id, r, event_type) for r in _extract_positive_rules(dict(job), label, event_type)]
        con.execute(
            "INSERT INTO positive_events(job_key,profile_id,event_type,created_at) VALUES(?,?,?,?)",
            (job_key, profile_id, event_type, _now()),
        )
    return {
        "job_key": job_key,
        "profile_id": profile_id,
        "event_type": event_type,
        "created": True,
        "positive_rule_ids": ids,
    }


def _origin_profiles(job_key):
    from .profile_store import get_profile

    with connection() as con:
        rows = con.execute(
            "SELECT DISTINCT profile_id FROM positive_events WHERE job_key=? AND event_type='suitable'", (job_key,)
        ).fetchall()
    if rows:
        return [int(r["profile_id"]) for r in rows]
    default = get_profile()
    return [default["id"]] if default else [1]


def sync_application_events(profile_ids=None, user_id=None):
    ensure_positive_schema()
    owner = "admin" if user_id is None else f"user:{int(user_id)}"
    with connection() as con:
        rows = con.execute(
            """SELECT job_key,status FROM applications
               WHERE owner_key=? AND status IN ('applied','interview','offer')""",
            (owner,),
        ).fetchall()
    milestones = {
        "applied": ("applied",),
        "interview": ("applied", "interview"),
        "offer": ("applied", "interview", "offer"),
    }
    created = 0
    allowed = set(profile_ids or [])
    for row in rows:
        origins = _origin_profiles(row["job_key"])
        origins = [p for p in origins if not allowed or p in allowed]
        for pid in origins:
            for event in milestones[row["status"]]:
                created += 1 if record_positive_event(row["job_key"], event, pid)["created"] else 0
    return created


def list_positive_rules(profile_id=None):
    ensure_positive_schema()
    where = ""
    params = []
    if profile_id:
        where = "WHERE profile_id=?"
        params = [profile_id]
    with connection() as con:
        rows = con.execute(
            f"SELECT * FROM positive_rules {where} ORDER BY enabled DESC,evidence_count DESC,weight DESC,term", params
        ).fetchall()
    return [{**dict(r), "enabled": bool(r["enabled"])} for r in rows]


def set_positive_rule_enabled(rule_id, enabled, user_id=None):
    with connection() as con:
        con.execute(
            """UPDATE positive_rules SET enabled=?,updated_at=? WHERE id=? AND profile_id IN
               (SELECT id FROM search_profiles WHERE user_id IS ?)""",
            (int(enabled), _now(), rule_id, user_id),
        )


def delete_positive_rule(rule_id, user_id=None):
    with connection() as con:
        con.execute(
            """DELETE FROM positive_rules WHERE id=? AND profile_id IN
               (SELECT id FROM search_profiles WHERE user_id IS ?)""",
            (rule_id, user_id),
        )


def apply_positive_boost(job, base_score, profile_id=1):
    ensure_positive_schema()
    with connection() as con:
        rules = con.execute(
            "SELECT scope,term,weight FROM positive_rules WHERE enabled=1 AND profile_id=?", (profile_id,)
        ).fetchall()
    fields = {
        "title": _normalise(getattr(job, "title", "")),
        "company": _normalise(getattr(job, "company", "")),
        "location": _normalise(getattr(job, "location", "")),
        "description": _normalise(f"{getattr(job, 'title', '')} {getattr(job, 'description', '')}"),
        "language": getattr(job, "language_label", "") or "",
    }
    boost = 0
    reasons = []
    for r in rules:
        if r["term"] and r["term"] in fields.get(r["scope"], ""):
            boost += int(r["weight"])
            reasons.append(f"preferred: {r['scope']} '{r['term']}' +{r['weight']}")
    boost = min(30, boost)
    return min(100, int(base_score) + boost), reasons


def positive_stats(profile_id=None):
    ensure_positive_schema()
    params = []
    pf = ""
    if profile_id:
        pf = " WHERE profile_id=?"
        params = [profile_id]
    with connection() as con:
        events = con.execute("SELECT COUNT(*) FROM positive_events" + pf, params).fetchone()[0]
        rules = con.execute(
            "SELECT COUNT(*) FROM positive_rules" + (pf + " AND " if pf else " WHERE ") + "enabled=1", params
        ).fetchone()[0]
        interviews = con.execute(
            "SELECT COUNT(*) FROM positive_events" + (pf + " AND " if pf else " WHERE ") + "event_type='interview'",
            params,
        ).fetchone()[0]
        offers = con.execute(
            "SELECT COUNT(*) FROM positive_events" + (pf + " AND " if pf else " WHERE ") + "event_type='offer'", params
        ).fetchone()[0]
    return {
        "positive_events": events,
        "positive_rules": rules,
        "learned_interviews": interviews,
        "learned_offers": offers,
    }
