from app import db
from app.matching_diagnostics import diagnose_job, list_benchmarks, run_benchmarks, save_benchmark
from app.profile_store import ensure_profile_schema, get_profile, save_profile
from app.search_job_store import ensure_search_job_schema, get_search_job, save_search_job


def setup(tmp_path, monkeypatch, *, role_level="technician"):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    ensure_profile_schema()
    profile_id = save_profile(
        {
            "name": "Quality Technician Berlin",
            "slug": "quality-technician-berlin",
            "enabled": True,
            "is_default": True,
            "target_location": "Berlin",
            "location_terms": ["berlin"],
            "min_score": 35,
            "min_language_score": 0,
            "language_weight": 0,
            "current_german_level": "a2",
            "current_english_level": "c1",
            "max_german_requirement": "b1",
            "preferred_weekly_hours": None,
            "availability": "any",
            "role_level": role_level,
            "show_b2_stretch": True,
            "hide_german_heavy": False,
            "prefer_german_growth": True,
            "content_languages": ["de", "en", "mixed"],
            "keywords": {
                "search": {"qualitätsprüfer": 0, "quality inspector": 0},
                "title": {"qualitätsprüfer": 40, "quality inspector": 40},
                "format": {"vollzeit": 10},
                "skill": {"qualität": 5},
                "blocklist": {"software": -100},
            },
        }
    )
    ensure_search_job_schema()
    job_id = save_search_job(
        {
            "name": "Technician",
            "profile_id": profile_id,
            "inherit_location": True,
            "employment_mode": "prefer",
        }
    )
    return get_search_job(job_id), get_profile(profile_id)


def test_diagnostic_reports_exact_first_failed_gate(tmp_path, monkeypatch):
    search_job, profile = setup(tmp_path, monkeypatch)
    diagnosis = diagnose_job(
        {
            "url": "https://example.com/software",
            "title": "Software Quality Engineer",
            "company": "Example",
            "location": "Berlin",
            "description": "Full-time software testing and QA automation.",
        },
        search_job,
        profile,
    )
    assert diagnosis["eligible"] is False
    assert diagnosis["first_failure"] == "blocklist"
    assert diagnosis["stages"][0]["detail"] == "Matched: software"


def test_benchmark_measures_precision_and_recall(tmp_path, monkeypatch):
    search_job, profile = setup(tmp_path, monkeypatch)
    payload = {
        "url": "https://example.com/inspector",
        "title": "Qualitätsprüfer",
        "company": "Example",
        "location": "Berlin",
        "description": "Vollzeit Qualitätskontrolle in der Produktion.",
        "expected_relevant": True,
    }
    diagnosis = diagnose_job(payload, search_job, profile)
    assert diagnosis["eligible"] is True
    benchmark_id = save_benchmark(payload, search_job, profile, diagnosis)
    assert benchmark_id > 0
    assert save_benchmark(payload, search_job, profile, diagnosis) == benchmark_id
    assert len(list_benchmarks(search_job["id"])) == 1
    result = run_benchmarks(search_job, profile)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["failures"] == []
