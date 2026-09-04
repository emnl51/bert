import asyncio

import pytest

from app.models import Job
from app import search_job_service as service


PROFILE = {
    "id": 7,
    "name": "Industrial engineering / Part-time",
    "slug": "industrial-part-time",
    "target_location": "Berlin",
    "location_terms": ["berlin"],
    "min_score": 35,
    "min_language_score": 30,
    "language_weight": 35,
    "current_german_level": "b1",
    "max_german_requirement": "b1",
    "prefer_german_growth": True,
    "hide_german_heavy": False,
    "show_b2_stretch": True,
    "keywords": {
        "search": {"process engineer part time": 0, "quality engineer part time": 0},
        "title": {"process engineer": 35, "quality engineer": 35},
        "format": {"part time": 12, "teilzeit": 12},
        "skill": {"spc": 8, "fmea": 8, "sap": 6},
        "allowlist": {"manufacturing": 10},
        "blocklist": {},
        "negative": {},
    },
}


@pytest.mark.parametrize(
    ("employment_mode", "expected_matches", "process_tier", "employment_filtered"),
    (("prefer", 2, "stretch", 1), ("strict", 1, "excluded", 2)),
)
def test_pipeline_separates_role_relevance_from_working_time_constraints(
    monkeypatch, employment_mode, expected_matches, process_tier, employment_filtered
):
    search_job = {
        "id": 11,
        "user_id": None,
        "name": "Engineering discovery",
        "profile_id": PROFILE["id"],
        "inherit_location": True,
        "target_location": "Berlin",
        "location_terms": [],
        "search_terms": [],
        "allowlist_terms": None,
        "blocklist_terms": None,
        "source_ids": [],
        "employment_mode": employment_mode,
        "min_score_override": None,
        "min_language_score_override": None,
        "min_cv_match": 58,
        "max_results": 20,
        "notify_email": False,
        "notify_telegram": False,
    }
    jobs = [
        Job(
            source="test",
            external_id="software",
            title="Software Quality Engineer",
            company="Cloud Co",
            location="Berlin",
            url="https://example.com/software",
            description="English-speaking cloud test automation with SAP integrations.",
        ),
        Job(
            source="test",
            external_id="process",
            title="Process Engineer – Cleaning & Etching",
            company="ASML",
            location="Berlin",
            url="https://example.com/process",
            description=(
                "Full-time manufacturing process ownership with SPC, FMEA, yield improvement. "
                "The international team works in English."
            ),
        ),
        Job(
            source="test",
            external_id="quality-short",
            title="Quality Engineer Part Time",
            company="Hach",
            location="Berlin",
            url="https://example.com/quality-short",
            description="Part-time role in an English-speaking team.",
        ),
        Job(
            source="test",
            external_id="quality-unknown-time",
            title="Quality Engineer",
            company="Example Manufacturing",
            location="Berlin",
            url="https://example.com/quality-unknown-time",
            description="Manufacturing quality systems with SPC and FMEA in an English-speaking team.",
        ),
    ]
    writes = []

    async def fetch_all(_sources, _terms, _location):
        return jobs, []

    monkeypatch.setattr(service, "get_search_job_any", lambda *_args, **_kwargs: search_job)
    monkeypatch.setattr(service, "acquire_search_job_lock", lambda *_args: True)
    monkeypatch.setattr(service, "create_search_job_run", lambda *_args: 19)
    monkeypatch.setattr(service, "finish_search_job_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "release_search_job_lock", lambda *_args: None)
    monkeypatch.setattr(service, "runtime_config", lambda *_args: {})
    monkeypatch.setattr(service, "get_profile", lambda *_args, **_kwargs: PROFILE)
    monkeypatch.setattr(service, "sync_application_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "candidate_for_search_job",
        lambda *_args, **_kwargs: {"id": 3, "name": "Test Candidate"},
    )
    monkeypatch.setattr(service, "_selected_sources", lambda *_args: [])
    monkeypatch.setattr(service, "fetch_all_jobs", fetch_all)
    monkeypatch.setattr(service, "apply_learned_penalty", lambda _job, score, **_kwargs: (score, []))
    monkeypatch.setattr(service, "apply_positive_boost", lambda _job, score, **_kwargs: (score, []))
    monkeypatch.setattr(service, "upsert_job", lambda *_args: True)
    monkeypatch.setattr(service, "upsert_language_fit", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "upsert_profile_score",
        lambda job, _profile_id, **kwargs: writes.append((job.external_id, job.match_tier, kwargs)),
    )
    monkeypatch.setattr(service, "mark_search_job_seen", lambda *_args: True)
    monkeypatch.setattr(
        service,
        "analyze_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("sparse descriptions must be deferred")),
    )

    result = asyncio.run(service.run_search_job(search_job["id"]))

    assert result["matches"] == expected_matches
    assert result["filtered"]["role"] == 1
    assert ("software", "excluded", {"role_relevant": False, "match_tier": "excluded"}) in writes
    assert result["filtered"]["employment"] == employment_filtered
    assert ("process", process_tier, {"role_relevant": True, "match_tier": process_tier}) in writes
    assert ("quality-short", "stretch", {"role_relevant": True, "match_tier": "stretch"}) in writes
    assert (
        "quality-unknown-time",
        "excluded",
        {"role_relevant": True, "match_tier": "excluded"},
    ) in writes
