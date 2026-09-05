from collections import defaultdict

from app import db
from app.service import _merge_provider_diagnostics
from app.source_analytics import (
    ensure_source_analytics_schema,
    query_quality_summary,
    save_query_run_stats,
    save_search_job_source_stats,
    save_source_run_stats,
    search_job_source_summary,
    source_quality_summary,
)


def test_source_quality_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_source_analytics_schema()
    save_source_run_stats(
        1,
        {
            "JobSpy / linkedin": {
                "fetched": 100,
                "unique_jobs": 90,
                "job_fit": 40,
                "language_fit": 35,
                "recommended": 20,
                "new_matches": 10,
                "provider_raw": 130,
                "provider_duplicates": 30,
                "filtered_inactive": 2,
                "filtered_stale": 20,
                "filtered_arrangement": 3,
                "filtered_location": 5,
                "provider_accepted": 70,
            }
        },
    )
    row = source_quality_summary(20)[0]
    assert row["source"] == "JobSpy / linkedin"
    assert row["quality_pct"] == 20.0
    assert row["new_yield_pct"] == 10.0
    assert row["dedupe_pct"] == 10.0
    assert row["provider_raw"] == 130
    assert row["provider_duplicates"] == 30
    assert row["filtered_inactive"] == 2
    assert row["filtered_stale"] == 20
    assert row["filtered_arrangement"] == 3
    assert row["filtered_location"] == 5
    assert row["provider_accepted"] == 70


def test_source_analytics_migrates_existing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    with db.connection() as con:
        con.execute("DROP TABLE IF EXISTS source_run_stats")
        con.execute(
            """CREATE TABLE source_run_stats (
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
               )"""
        )

    ensure_source_analytics_schema()

    with db.connection() as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(source_run_stats)").fetchall()}
    assert {
        "provider_raw",
        "provider_duplicates",
        "filtered_inactive",
        "filtered_stale",
        "filtered_arrangement",
        "filtered_location",
        "provider_accepted",
    } <= columns


def test_source_analytics_ui_explains_provider_filter_counts():
    text = open("app/source-analytics-ui.js", encoding="utf-8").read()
    assert "Provider filters" in text
    assert "provider_raw" in text
    assert "filtered_inactive" in text
    assert "filtered_stale" in text
    assert "filtered_arrangement" in text
    assert "filtered_location" in text


def test_provider_diagnostics_accumulate_for_sources_sharing_a_name_and_are_consumed_once():
    stats = defaultdict(lambda: defaultdict(int))
    sources = [
        {
            "name": "Kleinanzeigen Jobs",
            "_provider_diagnostics": {"provider_raw": 10, "provider_duplicates": 2, "provider_accepted": 6},
        },
        {
            "name": "Kleinanzeigen Jobs",
            "_provider_diagnostics": {"provider_raw": 8, "provider_duplicates": 1, "provider_accepted": 5},
        },
    ]

    _merge_provider_diagnostics(stats, sources)
    _merge_provider_diagnostics(stats, sources)

    assert stats["Kleinanzeigen Jobs"]["provider_raw"] == 18
    assert stats["Kleinanzeigen Jobs"]["provider_duplicates"] == 3
    assert stats["Kleinanzeigen Jobs"]["provider_accepted"] == 11
    assert all("_provider_diagnostics" not in source for source in sources)


def test_search_job_source_and_query_funnels_report_health(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    for run_id in (1, 2, 3):
        save_search_job_source_stats(
            run_id,
            7,
            {
                "productive": {"fetched": 10, "recommended": 3, "new_matches": 1},
                "empty": {"fetched": 0},
            },
        )
        save_query_run_stats(
            run_id,
            7,
            {
                "quality inspector": {"fetched": 10, "recommended": 2, "new_matches": 1},
                "weak query": {"fetched": 100, "recommended": 1, "new_matches": 0},
            },
        )

    sources = {row["source"]: row for row in search_job_source_summary(7)}
    queries = {row["query"]: row for row in query_quality_summary(7)}
    assert sources["productive"]["status"] == "productive"
    assert sources["empty"]["status"] == "no_results"
    assert queries["quality inspector"]["status"] == "productive"
    assert queries["weak query"]["status"] == "low_yield"
