from app.models import Job
from app.ranker import blocklist_matches, score_job

KEYWORDS = {
    "title": {"supply chain": 32, "procurement": 30},
    "format": {"werkstudent": 30, "working student": 30, "teilzeit": 12},
    "skill": {"sap": 7, "power bi": 6, "supplier": 5},
    "negative": {"developer": -25},
    "search": {},
}
LOCATIONS = ["berlin", "potsdam", "hennigsdorf"]


def test_good_werkstudent_match_scores_high():
    job = Job(
        source="test",
        external_id="1",
        title="Werkstudent Supply Chain",
        company="Example",
        location="Berlin",
        url="https://example.com",
        description="Support supplier projects using SAP and Power BI.",
    )
    score, reasons = score_job(job, KEYWORDS, LOCATIONS)
    assert score >= 80
    assert any("supply chain" in r for r in reasons)


def test_unrelated_role_scores_lower():
    job = Job(
        source="test",
        external_id="2",
        title="Software Developer",
        company="Example",
        location="Berlin",
        url="https://example.com",
        description="Full-time backend role.",
    )
    score, _ = score_job(job, KEYWORDS, LOCATIONS)
    assert score < 20


def test_allowlist_can_only_add_positive_points():
    job = Job(
        source="test",
        external_id="3",
        title="Process Engineer",
        company="Example",
        location="Berlin",
        url="https://example.com/3",
        description="Automotive manufacturing and IATF 16949",
    )
    baseline, _ = score_job(job, {**KEYWORDS, "allowlist": {}}, LOCATIONS)
    boosted, reasons = score_job(
        job,
        {**KEYWORDS, "allowlist": {"automotive": 15, "iatf 16949": -50}},
        LOCATIONS,
    )
    assert boosted == baseline + 15
    assert "allowlist: automotive" in reasons
    assert not any("iatf 16949" in reason for reason in reasons)


def test_blocklist_reports_hard_exclusion_matches():
    job = Job(
        source="test",
        external_id="4",
        title="Software Developer",
        company="Example",
        location="Berlin",
        url="https://example.com/4",
        description="Backend platform role",
    )
    assert blocklist_matches(job, {"blocklist": {"software developer": -100}}) == ["software developer"]
