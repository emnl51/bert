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


def test_nebenjob_and_studentenjob_are_confirmed_work_types():
    for title in ("Nebenjob Einkauf", "Studentenjob Supply Chain"):
        ok, label, _ = assess_employment_fit(job(title), PROFILE, strict=False)
        assert ok is True
        assert label == "part_time"


def test_explicit_full_time_is_rejected():
    ok, label, reasons = assess_employment_fit(
        job("Supply Chain Specialist", "Employment type: fulltime. Permanent position."), PROFILE
    )
    assert ok is False
    assert label == "full_time"
    assert "employment mismatch: full-time" in reasons


def test_unknown_format_is_always_rejected_for_part_time_profile():
    vacancy = job("Supply Chain Specialist", "International procurement and SAP responsibilities.")

    for strict in (False, True):
        ok, label, reasons = assess_employment_fit(vacancy, PROFILE, strict=strict)
        assert ok is False
        assert label == "unclear"
        assert any("not confirmed" in r for r in reasons)


def test_unknown_format_can_remain_a_preference_only_for_full_time_profile():
    profile = {
        "name": "Quality engineering / Full-time",
        "slug": "quality-full-time",
        "keywords": {"format": {"Vollzeit": 16, "full time": 16}},
    }
    vacancy = job("Quality Engineer", "Manufacturing quality systems and supplier development.")

    assert assess_employment_fit(vacancy, profile, strict=False)[:2] == (True, "unclear")
    assert assess_employment_fit(vacancy, profile, strict=True)[:2] == (False, "unclear")


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
    terms = search_terms_for_profile(mixed)
    assert terms[0] == "qualitätsprüfer"
    assert "Qualitätsprüfer Vollzeit" in terms
    assert "Qualitätsprüfer Teilzeit" in terms
    assert assess_employment_fit(job("Qualitätsprüfer Vollzeit"), mixed)[0] is True
    assert assess_employment_fit(job("Qualitätsprüfer Teilzeit"), mixed)[0] is True
    assert assess_employment_fit(job("Qualitätsprüfer", "Bauteile prüfen."), mixed, strict=False)[:2] == (
        False,
        "unclear",
    )


def test_first_class_hours_and_availability_are_constraints_or_preferences():
    profile = {
        "name": "Quality technician",
        "slug": "quality-technician",
        "preferred_weekly_hours": 20,
        "availability": "afternoon",
        "keywords": {"format": {"Vollzeit": 16, "Teilzeit": 16}},
    }
    vacancy = job("Qualitätsprüfer", "Teilzeit, 30 Stunden pro Woche am Vormittag.")

    strict = assess_employment_fit(vacancy, profile, strict=True)
    preferred = assess_employment_fit(vacancy, profile, strict=False)

    assert strict[0] is False
    assert preferred[0] is True
    assert any("exceeds preferred 20" in reason for reason in preferred[2])
    assert "employment mismatch: afternoon availability not confirmed" in preferred[2]


def test_mixed_hours_profile_does_not_admit_student_only_jobs_without_enrollment():
    mixed = {
        "name": "Quality engineering / Full-time and part-time",
        "slug": "quality-both",
        "keywords": {"format": {"Vollzeit": 16, "Teilzeit": 16}},
    }
    result = assess_employment_fit(job("Werkstudent Quality Engineering"), mixed, strict=False)
    assert result[0] is False
    assert result[1] == "student_only"

    body_only = assess_employment_fit(
        job("Quality Engineering Assistant", "Employment type: working student; enrollment is required."),
        mixed,
        strict=False,
    )
    assert body_only[0] is False
    assert body_only[1] == "student_only"


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
    assert terms[0] == "qualitätskontrolle"
    assert "quality engineer" in terms[:6]
    assert any("quality" in term and "part time" in term for term in terms)
    assert any(
        "arbeitsvorbereitung" in term or "produktionsplanung" in term or "produktionsplaner" in term for term in terms
    )
    assert any("technical" in term or "sachbearbeitung" in term for term in terms[:7])
    assert not any("werkstudent" in term or "supply chain" in term for term in terms)


def test_preference_mode_keeps_full_time_role_as_a_visible_stretch():
    vacancy = job("Process Engineer", "Employment type: full-time, 40 hours per week.")
    strict = assess_employment_fit(vacancy, ENGINEERING_PROFILE, strict=True)
    preferred = assess_employment_fit(vacancy, ENGINEERING_PROFILE, strict=False)
    assert strict[0] is False
    assert preferred[0] is True
    assert preferred[1] == "full_time"
    assert "employment mismatch: full-time" in preferred[2]


def test_full_time_profile_can_prefer_or_strictly_require_its_working_arrangement():
    profile = {
        "name": "Industrial engineering / Full-time",
        "slug": "industrial-full-time",
        "keywords": {"format": {"full-time": 16, "vollzeit": 16}},
    }
    full_time = job("Process Engineer", "Employment type: full-time, 40 hours per week.")
    part_time = job("Process Engineer Teilzeit", "20 Stunden pro Woche.")
    assert assess_employment_fit(full_time, profile, strict=True)[:2] == (True, "full_time")
    assert assess_employment_fit(part_time, profile, strict=True)[0] is False
    preferred = assess_employment_fit(part_time, profile, strict=False)
    assert preferred[0] is True
    assert preferred[1] == "part_time"
    assert "employment mismatch: part-time/student" in preferred[2]


def test_first_provider_queries_cover_each_industrial_role_before_schedule_variants():
    profile = {
        "name": "Industrial engineering / Part-time",
        "slug": "industrial-part-time",
        "target_location": "Berlin",
        "location_terms": ["berlin"],
        "keywords": {
            "search": {
                "part time quality engineer berlin": 0,
                "supplier quality engineer teilzeit berlin": 0,
                "quality assurance engineer part time berlin": 0,
                "teilzeit process engineer berlin": 0,
                "lackieringenieur teilzeit berlin": 0,
                "production planner part time berlin": 0,
            },
            "title": {
                "process engineer": 35,
                "quality engineer": 35,
                "lackieringenieur": 32,
                "production planner": 32,
            },
            "format": {"teilzeit": 12, "part time": 12},
        },
    }
    terms = search_terms_for_profile(profile)
    first_six = terms[:6]
    assert "process engineer" in first_six
    assert "quality engineer" in first_six
    assert "lackieringenieur" in first_six
    assert "production planner" in first_six
    assert not any("part time" in term or "teilzeit" in term for term in first_six)


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
