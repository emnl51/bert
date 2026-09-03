from app.models import Job
from app.ranker import assess_role_relevance, score_job


KEYWORDS = {
    "search": {
        "process engineer": 0,
        "quality engineer": 0,
        "production planner": 0,
        "coating engineer": 0,
    },
    "title": {
        "process engineer": 35,
        "quality engineer": 35,
        "production planner": 32,
        "coating engineer": 32,
        "lackieringenieur": 32,
    },
    "format": {"teilzeit": 12, "part time": 12},
    "skill": {
        "fmea": 8,
        "spc": 8,
        "root cause": 7,
        "lean": 6,
        "six sigma": 6,
        "process optimization": 7,
    },
    "allowlist": {"automotive": 12, "manufacturing": 10},
    "negative": {},
}


def vacancy(external_id: str, title: str, description: str) -> Job:
    return Job(
        source="benchmark",
        external_id=external_id,
        title=title,
        company="Example",
        location="Berlin",
        url=f"https://example.com/{external_id}",
        description=description,
    )


def test_manual_hach_quality_engineer_is_a_direct_high_fit_match():
    job = vacancy(
        "hach",
        "Quality Engineer (m/w/d)",
        "Industrial quality for logistics, corrective actions, root cause, 8D, Ishikawa and cross-functional KPIs.",
    )
    assessment = assess_role_relevance(job, KEYWORDS)
    score, reasons = score_job(job, KEYWORDS, ["berlin"])
    assert assessment.relevant is True
    assert assessment.confidence == "direct"
    assert score >= 70
    assert "role family: quality" in reasons


def test_manual_asml_cleaning_and_etching_role_is_not_mistaken_for_cleaning_work():
    job = vacancy(
        "asml",
        "Process Engineer – Cleaning & Etching / Prozessingenieur:in Reinigungs- und Ätztechnologien",
        "Own manufacturing cleaning and etching processes using Lean, Six Sigma, SPC, FMEA, yield and cycle time.",
    )
    assessment = assess_role_relevance(job, KEYWORDS)
    score, _ = score_job(job, KEYWORDS, ["berlin"])
    assert assessment.relevant is True
    assert "process" in assessment.matched_families
    assert score >= 75


def test_software_quality_title_is_rejected_without_industrial_domain_evidence():
    job = vacancy(
        "software",
        "Software Quality Engineer",
        "Build cloud test automation for backend services using Python and Kubernetes.",
    )
    assessment = assess_role_relevance(job, KEYWORDS)
    assert assessment.relevant is False
    assert assessment.confidence == "conflict"


def test_technician_profile_rejects_engineering_and_management_titles():
    technician_keywords = {
        **KEYWORDS,
        "title": {"quality technician": 35, "quality engineer": 35, "qualitätsprüfer": 35},
    }
    technician = vacancy("technician", "Quality Technician", "Inspect manufactured components.")
    engineer = vacancy("engineer-level", "Quality Engineer", "Quality systems in manufacturing.")
    manager = vacancy("manager-level", "Quality Manager", "Lead the plant quality department.")

    assert assess_role_relevance(technician, technician_keywords, role_level="technician").relevant is True
    assert assess_role_relevance(engineer, technician_keywords, role_level="technician").confidence == "level_conflict"
    assert assess_role_relevance(manager, technician_keywords, role_level="technician").confidence == "level_conflict"


def test_student_profile_requires_student_title_signal():
    student = vacancy("student", "Working Student Supply Chain", "Support procurement operations.")
    professional = vacancy("professional", "Supply Chain Specialist", "Manage procurement operations.")
    keywords = {**KEYWORDS, "title": {"working student supply chain": 35, "supply chain specialist": 35}}

    assert assess_role_relevance(student, keywords, role_level="student").relevant is True
    assert assess_role_relevance(professional, keywords, role_level="student").confidence == "level_conflict"


def test_generic_production_and_hr_jobs_cannot_be_rescued_by_soft_signals():
    production_worker = vacancy(
        "worker",
        "Production Worker",
        "Full-time manufacturing work with quality checks at a Berlin plant.",
    )
    hr_partner = vacancy(
        "hr",
        "HR Business Partner",
        "Support a manufacturing plant, continuous improvement, Lean and root cause workshops.",
    )
    assert assess_role_relevance(production_worker, KEYWORDS).relevant is False
    assert assess_role_relevance(hr_partner, KEYWORDS).relevant is False


def test_generic_engineer_title_can_use_strong_description_role_evidence():
    job = vacancy(
        "engineer-ii",
        "Engineer II",
        "Responsible for process engineering, process optimization, PFMEA and SPC in automotive manufacturing.",
    )
    assessment = assess_role_relevance(job, KEYWORDS)
    assert assessment.relevant is True
    assert assessment.confidence == "supported"
    assert "process" in assessment.matched_families


def test_unmapped_search_role_still_requires_direct_title_evidence_and_scores_it():
    keywords = {
        "search": {"mechanical engineer": 0},
        "title": {},
        "format": {},
        "skill": {},
        "allowlist": {},
        "negative": {},
    }
    mechanical = vacancy("mechanical", "Senior Mechanical Engineer", "Design industrial equipment.")
    unrelated = vacancy("unrelated", "HR Manager", "Support an engineering organization.")
    assert assess_role_relevance(mechanical, keywords).relevant is True
    assert assess_role_relevance(unrelated, keywords).relevant is False
    assert score_job(mechanical, keywords, ["berlin"])[0] >= 40


def test_conflicting_occupation_is_allowed_when_the_profile_explicitly_requests_it():
    keywords = {
        "search": {"software engineer": 0},
        "title": {"software engineer": 35},
        "format": {},
        "skill": {},
        "allowlist": {},
        "negative": {},
    }
    assessment = assess_role_relevance(
        vacancy("explicit-software", "Senior Software Engineer", "Build distributed systems."),
        keywords,
    )
    assert assessment.relevant is True
    assert assessment.confidence == "direct"


def test_industrial_title_variants_expand_recall_without_generic_worker_terms():
    titles = (
        "Lieferantenqualitätsingenieur (m/w/d)",
        "Process Development Engineer",
        "Paint Shop Engineer",
        "Fertigungsplaner",
    )
    assert all(
        assess_role_relevance(vacancy(f"variant-{index}", title, "Automotive manufacturing."), KEYWORDS).relevant
        for index, title in enumerate(titles)
    )


def test_live_jobspy_noise_sample_is_rejected_by_role_gate():
    # Titles returned by the live Indeed adapter for the queries "quality engineer"
    # and "process engineer" on 2026-09-02. Provider-side search is intentionally
    # treated as candidate discovery, never as proof of role relevance.
    live_titles = (
        "Senior Android Engineer (m/f/d)",
        "Job Posting Title Construction Surveillance Technician",
        "Junior Software Engineer (all genders)",
        "Principal Software Engineer",
        "Applied Mathematician",
        "Head of Mass Spectrometry Core Facility (m/f/d)",
        "DevOps Engineer - CI/CD & Platform Engineering",
        "Senior Full-Stack Engineer - Team Agent",
        "Project Engineer (Utility BESS)",
        "Product Manager (DevTools & AI Reliability, remote)",
        "Senior Electronics Engineer EW (All Genders)",
        "Deployment Engineer, Google Cloud Public Sector",
        "Technical Project Manager, Carrier Integrations",
    )
    assessments = [
        assess_role_relevance(vacancy(f"live-{index}", title, "English-speaking role."), KEYWORDS)
        for index, title in enumerate(live_titles)
    ]
    assert not [assessment for assessment in assessments if assessment.relevant]
