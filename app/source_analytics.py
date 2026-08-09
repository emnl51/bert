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
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, source)
);
CREATE INDEX IF NOT EXISTS idx_source_run_stats_run ON source_run_stats(run_id DESC);
CREATE INDEX IF NOT EXISTS idx_source_run_stats_source ON source_run_stats(source);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_source_analytics_schema() -> None:
    with connection() as con:
        con.executescript(SOURCE_ANALYTICS_SCHEMA)


def save_source_run_stats(run_id: int, stats: dict[str, dict[str, int]]) -> None:
    ensure_source_analytics_schema()
    with connection() as con:
        for source, values in stats.items():
            con.execute(
                """INSERT INTO source_run_stats(
                       run_id,source,fetched,unique_jobs,job_fit,language_fit,recommended,new_matches,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,source) DO UPDATE SET
                       fetched=excluded.fetched,
                       unique_jobs=excluded.unique_jobs,
                       job_fit=excluded.job_fit,
                       language_fit=excluded.language_fit,
                       recommended=excluded.recommended,
                       new_matches=excluded.new_matches,
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
                    _now(),
                ),
            )


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
            f"""SELECT run_id,source,fetched,unique_jobs,job_fit,language_fit,recommended,new_matches,created_at
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
