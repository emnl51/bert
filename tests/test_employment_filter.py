from app.employment_filter import assess_employment_fit, search_terms_for_profile
from app.models import Job


PROFILE = {
    "name": "Werkstudent / Part-time",
    "slug": "werkstudent",
    "keywords": {
        "search": {
            "werkstudent supply chain": 0,
            "werkstudent procurement": 0,
        },
        "format": {
            "werkstudent": 34,
            "working student": 34,
            "teilzeit": 14,
            "part-time": 14,
            "part time": 14,
        },
    },
}


def job(title, description=""):
    return Job(
        source="test",
        external_id=title,
        title=title,
        company="Example GmbH",
        location="Berlin",
        url="https://example.com/job",
        description=description,
    )


def test_werkstudent_is_eligible():
    ok, label, reasons = assess_employment_fit(job("Werkstudent Supply Chain"), PROFILE)
    assert ok is True
    assert label == "part_time"
    assert any("confirmed" in r for r in reasons)


def test_minijob_is_eligible_even_if_not_in_old_profile_json():
    ok, label, _ = assess_employment_fit(job("Logistik Minijob Berlin"), PROFILE)
    assert ok is True
    assert label == "part_time"


def test_explicit_full_time_is_rejected():
    ok, label, reasons = assess_employment_fit(
        job("Supply Chain Specialist", "Employment type: fulltime. Permanent position."), PROFILE
    )
    assert ok is False
    assert label == "full_time"
    assert "employment mismatch: full-time" in reasons


def test_unknown_format_is_rejected_for_strict_part_time_profile():
    ok, label, reasons = assess_employment_fit(
        job("Supply Chain Specialist", "International procurement and SAP responsibilities."), PROFILE
    )
    assert ok is False
    assert label == "unclear"
    assert any("not confirmed" in r for r in reasons)


def test_mixed_full_and_part_time_profile_accepts_both_and_keeps_queries():
    mixed = {
        "name": "Quality inspection / Full-time and part-time",
        "slug": "quality-both",
        "keywords": {
            "search": {
                "Qualitätsprüfer Vollzeit": 0,
                "Qualitätsprüfer Teilzeit": 0,
            },
            "format": {"Vollzeit": 16, "Teilzeit": 16},
        },
    }
    assert search_terms_for_profile(mixed) == ["Qualitätsprüfer Vollzeit", "Qualitätsprüfer Teilzeit"]
    assert assess_employment_fit(job("Qualitätsprüfer Vollzeit"), mixed)[0] is True
    assert assess_employment_fit(job("Qualitätsprüfer Teilzeit"), mixed)[0] is True


def test_part_time_signal_wins_over_full_time_boilerplate():
    ok, label, _ = assess_employment_fit(
        job("Working Student Operations", "This is a working student role. Our company also has full-time employees."),
        PROFILE,
    )
    assert ok is True
    assert label == "part_time"


def test_part_time_search_terms_are_diversified_before_configured_terms():
    terms = search_terms_for_profile(PROFILE)
    assert terms[:3] == [
        "werkstudent supply chain",
        "part time supply chain",
        "minijob logistik",
    ]
    assert "werkstudent procurement" in terms
    assert not any("manager berlin" in term for term in terms)


ENGINEERING_PROFILE = {
    "name": "Engineering support / Part-time",
    "slug": "engineering-part-time",
    "keywords": {
        "search": {"qualitätskontrolle teilzeit": 0},
        "title": {"quality control": 30, "production planning": 28, "technical office": 25},
        "format": {"teilzeit": 20, "minijob": 18, "part time": 16},
    },
}


def test_engineering_profile_gets_its_own_bilingual_role_queries():
    terms = search_terms_for_profile(ENGINEERING_PROFILE)
    assert terms[0] == "qualitätskontrolle teilzeit"
    assert any("quality" in term and "part time" in term for term in terms)
    assert any("arbeitsvorbereitung" in term or "produktionsplanung" in term for term in terms)
    assert any("sachbearbeitung" in term for term in terms[:6])
    assert not any("werkstudent" in term or "supply chain" in term for term in terms)


def test_part_time_is_confirmed_from_weekly_hours_and_afternoon_schedule():
    ok, label, reasons = assess_employment_fit(
        job("Qualitätsprüfer", "Arbeitszeit: 15-20 Stunden pro Woche, nachmittags."), ENGINEERING_PROFILE
    )
    assert ok is True
    assert label == "part_time"
    assert "schedule: 20 hours/week" in reasons
    assert "schedule: afternoon/flexible" in reasons


def test_workload_percentage_and_afternoon_start_are_recognized():
    ok, label, reasons = assess_employment_fit(
        job("Technische Sachbearbeitung", "Pensum 50%, Arbeitsbeginn ab 14 Uhr."), ENGINEERING_PROFILE
    )
    assert ok is True
    assert label == "part_time"
    assert "schedule: 50% workload" in reasons
    assert "schedule: afternoon/flexible" in reasons


def test_student_only_jobs_do_not_match_non_student_engineering_profile():
    ok, label, _ = assess_employment_fit(
        job("Werkstudent Qualitätssicherung", "Teilzeit 20 Stunden"), ENGINEERING_PROFILE
    )
    assert ok is False
    assert label == "student_only"


def test_negated_part_time_is_not_counted_as_an_available_working_arrangement():
    ok, label, _ = assess_employment_fit(
        job("Qualitätsprüfung", "Keine Teilzeit. Vollzeit 40 Stunden."), ENGINEERING_PROFILE
    )
    assert ok is False
    assert label == "full_time"


def test_full_time_or_part_time_alternatives_remain_eligible():
    ok, label, _ = assess_employment_fit(
        job("Qualitätsprüfung", "Vollzeit oder Teilzeit möglich."), ENGINEERING_PROFILE
    )
    assert ok is True
    assert label == "part_time"
