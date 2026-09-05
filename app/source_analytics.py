from datetime import datetime, timezone
from .db import connection


SOURCE_ANALYTICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_run_stats (
    run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    fetched INTEGER NOT NULL DEFAULT 0,
    unique_jobs INTEGER NOT NULL DEFAULT 0,
    job_fit INTEGER NOT NULL DEFAULT 0,
    language_fit INTEGER NOT NULL DEFAULT 0,
    recommended INTEGER NOT NULL DEFAULT 0,
    new_matches INTEGER NOT NULL DEFAULT 0,
    provider_raw INTEGER NOT NULL DEFAULT 0,
    provider_duplicates INTEGER NOT NULL DEFAULT 0,
    filtered_inactive INTEGER NOT NULL DEFAULT 0,
    filtered_stale INTEGER NOT NULL DEFAULT 0,
    filtered_arrangement INTEGER NOT NULL DEFAULT 0,
    filtered_location INTEGER NOT NULL DEFAULT 0,
    provider_accepted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, source)
);
CREATE INDEX IF NOT EXISTS idx_source_run_stats_run ON source_run_stats(run_id DESC);
CREATE INDEX IF NOT EXISTS idx_source_run_stats_source ON source_run_stats(source);

CREATE TABLE IF NOT EXISTS query_run_stats (
    run_id INTEGER NOT NULL,
    user_id INTEGER,
    search_job_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    fetched INTEGER NOT NULL DEFAULT 0,
    recommended INTEGER NOT NULL DEFAULT 0,
    new_matches INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, query)
);
CREATE INDEX IF NOT EXISTS idx_query_run_stats_job
    ON query_run_stats(user_id, search_job_id, run_id DESC);

CREATE TABLE IF NOT EXISTS search_job_source_run_stats (
    run_id INTEGER NOT NULL,
    user_id INTEGER,
    search_job_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    fetched INTEGER NOT NULL DEFAULT 0,
    unique_jobs INTEGER NOT NULL DEFAULT 0,
    role_fit INTEGER NOT NULL DEFAULT 0,
    employment_fit INTEGER NOT NULL DEFAULT 0,
    language_fit INTEGER NOT NULL DEFAULT 0,
    recommended INTEGER NOT NULL DEFAULT 0,
    new_matches INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, search_job_id, source)
);
CREATE INDEX IF NOT EXISTS idx_search_job_source_stats_job
    ON search_job_source_run_stats(user_id, search_job_id, run_id DESC);
"""

DIAGNOSTIC_COLUMNS = (
    "provider_raw",
    "provider_duplicates",
    "filtered_inactive",
    "filtered_stale",
    "filtered_arrangement",
    "filtered_location",
    "provider_accepted",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_source_analytics_schema() -> None:
    with connection() as con:
        con.executescript(SOURCE_ANALYTICS_SCHEMA)
        columns = {row[1] for row in con.execute("PRAGMA table_info(source_run_stats)").fetchall()}
        for column in DIAGNOSTIC_COLUMNS:
            if column not in columns:
                con.execute(f"ALTER TABLE source_run_stats ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")


def save_source_run_stats(run_id: int, stats: dict[str, dict[str, int]]) -> None:
    ensure_source_analytics_schema()
    with connection() as con:
        for source, values in stats.items():
            con.execute(
                """INSERT INTO source_run_stats(
                       run_id,source,fetched,unique_jobs,job_fit,language_fit,recommended,new_matches,
                       provider_raw,provider_duplicates,filtered_inactive,filtered_stale,
                       filtered_arrangement,filtered_location,provider_accepted,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,source) DO UPDATE SET
                       fetched=excluded.fetched,
                       unique_jobs=excluded.unique_jobs,
                       job_fit=excluded.job_fit,
                       language_fit=excluded.language_fit,
                       recommended=excluded.recommended,
                       new_matches=excluded.new_matches,
                       provider_raw=excluded.provider_raw,
                       provider_duplicates=excluded.provider_duplicates,
                       filtered_inactive=excluded.filtered_inactive,
                       filtered_stale=excluded.filtered_stale,
                       filtered_arrangement=excluded.filtered_arrangement,
                       filtered_location=excluded.filtered_location,
                       provider_accepted=excluded.provider_accepted,
                       created_at=excluded.created_at""",
                (
                    run_id,
                    source,
                    int(values.get("fetched", 0)),
                    int(values.get("unique_jobs", 0)),
                    int(values.get("job_fit", 0)),
                    int(values.get("language_fit", 0)),
                    int(values.get("recommended", 0)),
                    int(values.get("new_matches", 0)),
                    int(values.get("provider_raw", 0)),
                    int(values.get("provider_duplicates", 0)),
                    int(values.get("filtered_inactive", 0)),
                    int(values.get("filtered_stale", 0)),
                    int(values.get("filtered_arrangement", 0)),
                    int(values.get("filtered_location", 0)),
                    int(values.get("provider_accepted", 0)),
                    _now(),
                ),
            )


def save_query_run_stats(
    run_id: int,
    search_job_id: int,
    stats: dict[str, dict[str, int]],
    user_id: int | None = None,
) -> None:
    ensure_source_analytics_schema()
    with connection() as con:
        for query, values in stats.items():
            con.execute(
                """INSERT INTO query_run_stats(
                       run_id,user_id,search_job_id,query,fetched,recommended,new_matches,created_at
                   ) VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,query) DO UPDATE SET
                       fetched=excluded.fetched,recommended=excluded.recommended,
                       new_matches=excluded.new_matches,created_at=excluded.created_at""",
                (
                    run_id,
                    user_id,
                    search_job_id,
                    query,
                    int(values.get("fetched", 0)),
                    int(values.get("recommended", 0)),
                    int(values.get("new_matches", 0)),
                    _now(),
                ),
            )


def save_search_job_source_stats(
    run_id: int,
    search_job_id: int,
    stats: dict[str, dict[str, int]],
    user_id: int | None = None,
) -> None:
    ensure_source_analytics_schema()
    with connection() as con:
        for source, values in stats.items():
            con.execute(
                """INSERT INTO search_job_source_run_stats(
                       run_id,user_id,search_job_id,source,fetched,unique_jobs,role_fit,
                       employment_fit,language_fit,recommended,new_matches,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,search_job_id,source) DO UPDATE SET
                       fetched=excluded.fetched,unique_jobs=excluded.unique_jobs,
                       role_fit=excluded.role_fit,employment_fit=excluded.employment_fit,
                       language_fit=excluded.language_fit,recommended=excluded.recommended,
                       new_matches=excluded.new_matches,created_at=excluded.created_at""",
                (
                    run_id,
                    user_id,
                    search_job_id,
                    source,
                    int(values.get("fetched", 0)),
                    int(values.get("unique_jobs", 0)),
                    int(values.get("role_fit", 0)),
                    int(values.get("employment_fit", 0)),
                    int(values.get("language_fit", 0)),
                    int(values.get("recommended", 0)),
                    int(values.get("new_matches", 0)),
                    _now(),
                ),
            )


def search_job_source_summary(search_job_id: int, last_runs: int = 20, user_id: int | None = None) -> list[dict]:
    ensure_source_analytics_schema()
    with connection() as con:
        rows = con.execute(
            """WITH recent AS (
                   SELECT DISTINCT run_id FROM search_job_source_run_stats
                   WHERE user_id IS ? AND search_job_id=? ORDER BY run_id DESC LIMIT ?
               )
               SELECT s.source,SUM(s.fetched) AS fetched,SUM(s.unique_jobs) AS unique_jobs,
                      SUM(s.role_fit) AS role_fit,SUM(s.employment_fit) AS employment_fit,
                      SUM(s.language_fit) AS language_fit,SUM(s.recommended) AS recommended,
                      SUM(s.new_matches) AS new_matches,COUNT(DISTINCT s.run_id) AS runs
               FROM search_job_source_run_stats s JOIN recent r ON r.run_id=s.run_id
               WHERE s.user_id IS ? AND s.search_job_id=? GROUP BY s.source
               ORDER BY recommended DESC,new_matches DESC,fetched DESC""",
            (user_id, search_job_id, max(1, min(int(last_runs), 200)), user_id, search_job_id),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        fetched = int(item["fetched"] or 0)
        item["quality_pct"] = round(int(item["recommended"] or 0) / fetched * 100, 1) if fetched else 0.0
        runs = int(item["runs"] or 0)
        if runs < 3:
            item["status"] = "insufficient_data"
        elif fetched == 0:
            item["status"] = "no_results"
        elif item["quality_pct"] < 3:
            item["status"] = "low_yield"
        else:
            item["status"] = "productive"
        result.append(item)
    return result


def query_quality_summary(search_job_id: int, last_runs: int = 20, user_id: int | None = None) -> list[dict]:
    ensure_source_analytics_schema()
    with connection() as con:
        rows = con.execute(
            """WITH recent AS (
                   SELECT DISTINCT run_id FROM query_run_stats
                   WHERE user_id IS ? AND search_job_id=? ORDER BY run_id DESC LIMIT ?
               )
               SELECT q.query,SUM(q.fetched) AS fetched,SUM(q.recommended) AS recommended,
                      SUM(q.new_matches) AS new_matches,COUNT(DISTINCT q.run_id) AS runs
               FROM query_run_stats q JOIN recent r ON r.run_id=q.run_id
               WHERE q.user_id IS ? AND q.search_job_id=? GROUP BY q.query
               ORDER BY recommended DESC,new_matches DESC,fetched DESC,q.query""",
            (user_id, search_job_id, max(1, min(int(last_runs), 200)), user_id, search_job_id),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        fetched = int(item["fetched"] or 0)
        item["quality_pct"] = round(int(item["recommended"] or 0) / fetched * 100, 1) if fetched else 0.0
        runs = int(item["runs"] or 0)
        if runs < 3:
            item["status"] = "insufficient_data"
        elif fetched == 0:
            item["status"] = "no_results"
        elif item["quality_pct"] < 3:
            item["status"] = "low_yield"
        else:
            item["status"] = "productive"
        result.append(item)
    return result


def list_source_run_stats(run_id: int | None = None, limit: int = 200) -> list[dict]:
    ensure_source_analytics_schema()
    where = ""
    params: list = []
    if run_id is not None:
        where = "WHERE run_id=?"
        params.append(run_id)
    params.append(max(1, min(int(limit), 1000)))
    with connection() as con:
        rows = con.execute(
            f"""SELECT run_id,source,fetched,unique_jobs,job_fit,language_fit,recommended,new_matches,
                       provider_raw,provider_duplicates,filtered_inactive,filtered_stale,
                       filtered_arrangement,filtered_location,provider_accepted,created_at
                FROM source_run_stats {where}
                ORDER BY run_id DESC,recommended DESC,fetched DESC
                LIMIT ?""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def source_quality_summary(last_runs: int = 20) -> list[dict]:
    ensure_source_analytics_schema()
    last_runs = max(1, min(int(last_runs), 200))
    with connection() as con:
        rows = con.execute(
            """WITH recent_runs AS (
                   SELECT DISTINCT run_id FROM source_run_stats ORDER BY run_id DESC LIMIT ?
               )
               SELECT s.source,
                      SUM(s.fetched) AS fetched,
                      SUM(s.unique_jobs) AS unique_jobs,
                      SUM(s.job_fit) AS job_fit,
                      SUM(s.language_fit) AS language_fit,
                      SUM(s.recommended) AS recommended,
                      SUM(s.new_matches) AS new_matches,
                      SUM(s.provider_raw) AS provider_raw,
                      SUM(s.provider_duplicates) AS provider_duplicates,
                      SUM(s.filtered_inactive) AS filtered_inactive,
                      SUM(s.filtered_stale) AS filtered_stale,
                      SUM(s.filtered_arrangement) AS filtered_arrangement,
                      SUM(s.filtered_location) AS filtered_location,
                      SUM(s.provider_accepted) AS provider_accepted,
                      COUNT(DISTINCT s.run_id) AS runs
               FROM source_run_stats s
               JOIN recent_runs r ON r.run_id=s.run_id
               GROUP BY s.source
               ORDER BY recommended DESC, fetched DESC""",
            (last_runs,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        fetched = int(item.get("fetched") or 0)
        unique_jobs = int(item.get("unique_jobs") or 0)
        item["quality_pct"] = round((int(item.get("recommended") or 0) / fetched * 100), 1) if fetched else 0.0
        item["new_yield_pct"] = round((int(item.get("new_matches") or 0) / fetched * 100), 1) if fetched else 0.0
        item["dedupe_pct"] = round((1 - unique_jobs / fetched) * 100, 1) if fetched else 0.0
        result.append(item)
    return result
