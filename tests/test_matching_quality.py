from app import intelligence as intel
from app.models import Job
from app.ranker import blocklist_matches, score_job
from app.search_job_service import deduplicate_jobs, passes_candidate_threshold
from app.text_match import contains_phrase, normalize_text


def vacancy(title: str, description: str = "") -> Job:
    return Job(
        source="test",
        external_id=title,
        title=title,
        company="Example",
        location="Berlin",
        url="https://example.com/job",
        description=description,
    )


def candidate(cv_text: str, skills=None) -> dict:
    return {
        "headline": "Automotive Process Engineer",
        "cv_text": cv_text,
        "skills": skills or [],
        "languages": {"English": "professional", "German": "B1"},
        "target_roles": ["Process Engineer"],
        "notes": "",
    }


def test_matching_normalization_removes_html_and_preserves_unicode():
    assert normalize_text("<p>Qualität&nbsp;&amp; PFMEA</p>") == "qualität & pfmea"
    assert contains_phrase("Erfahrung in Qualitätssicherung", "qualitätssicherung")


def test_short_skill_uses_word_boundaries_in_scoring_and_blocklists():
    job = vacancy("Process Engineer", "Work with Sapphire systems in Berlin")
    score, reasons = score_job(job, {"skill": {"sap": 30}}, ["berlin"])
    assert score == 12
    assert "skill: sap" not in reasons
    assert blocklist_matches(job, {"blocklist": {"sap": -100}}) == []


def test_negated_vacancy_terms_do_not_score_or_trigger_hard_block():
    job = vacancy("Process Engineer", "SAP is not required. This is not a software developer position.")
    score, reasons = score_job(job, {"skill": {"sap": 30}}, [])
    assert score == 0
    assert "skill: sap" not in reasons
    assert blocklist_matches(job, {"blocklist": {"software developer": -100}}) == []


def test_negated_candidate_skill_is_not_accepted_as_evidence():
    job = {"title": "Process Engineer", "description": "SAP experience required."}
    result = intel._deterministic(candidate("Automotive experience but no SAP experience."), job)
    sap = next(item for item in result["evidence"] if item["term"] == "sap")
    assert sap["status"] == "missing"


def test_later_affirmed_skill_wins_over_an_earlier_negated_reference():
    job = {"title": "Process Engineer", "description": "SAP experience required."}
    cv = "Earlier role had no SAP access. Later I completed SAP production planning projects."
    result = intel._deterministic(candidate(cv), job)
    sap = next(item for item in result["evidence"] if item["term"] == "sap")
    assert sap["status"] == "match"


def test_optional_requirement_is_explained_without_becoming_a_gap():
    job = {
        "title": "Process Engineer",
        "description": "PFMEA is required. SAP knowledge is a plus.",
    }
    result = intel._deterministic(candidate("12 years automotive experience with PFMEA."), job)
    sap_requirement = next(item for item in result["requirements"] if item["term"] == "sap")
    sap_evidence = next(item for item in result["evidence"] if item["term"] == "sap")
    assert sap_requirement["required"] is False
    assert sap_evidence["required"] is False
    assert sap_evidence["status"] == "missing"
    assert not any("sap" in gap.lower() for gap in result["gaps"])


def test_german_and_english_role_titles_share_a_role_family():
    job = {"title": "Produktionsplaner / Arbeitsvorbereitung", "description": "Plan production processes."}
    person = candidate("12 years manufacturing planning experience.")
    person["target_roles"] = ["Production Planner"]
    result = intel._deterministic(person, job)
    role = next(item for item in result["evidence"] if item["category"] == "role")
    assert role["status"] == "match"
    assert "production planning" in role["evidence"]


def test_duplicate_vacancies_keep_the_richer_description_in_stable_order():
    first = vacancy("Process Engineer", "Short")
    first.source = "source-a"
    first.external_id = "1"
    duplicate = vacancy(" Process  Engineer ", "A much richer PFMEA and SPC description")
    duplicate.source = "source-b"
    duplicate.external_id = "2"
    other = vacancy("Quality Engineer", "Quality role")
    unique = deduplicate_jobs([first, duplicate, other])
    assert len(unique) == 2
    assert unique[0].description == duplicate.description
    assert unique[1].title == "Quality Engineer"


def test_candidate_threshold_is_inclusive_and_clamped():
    assert passes_candidate_threshold({"cv_match": 58}, 58)
    assert not passes_candidate_threshold({"cv_match": 57}, 58)
    assert not passes_candidate_threshold(None, 0)
