from app.models import Job
from app.ranker import assess_language_fit, calculate_overall_score

PROFILE = {
    "primary_working_language": "English",
    "current_german_level": "a2_b1",
    "max_german_requirement": "b1",
    "prefer_german_growth": True,
}


def make_job(description: str) -> Job:
    return Job(
        source="test",
        external_id="lang",
        title="Working Student Supply Chain",
        company="Example",
        location="Berlin",
        url="https://example.com",
        description=description,
    )


def test_english_first_role_scores_high():
    score, label, reasons = assess_language_fit(
        make_job("Join our international team. Fluent English is required."),
        PROFILE,
    )
    assert label == "english_first"
    assert score >= 90
    assert any("English" in r for r in reasons)


def test_german_optional_is_growth_opportunity():
    score, label, reasons = assess_language_fit(
        make_job("Fluent English required. German is a plus."),
        PROFILE,
    )
    assert label == "german_growth"
    assert score >= 90
    assert any("optional" in r for r in reasons)


def test_b2_required_is_stretch_for_a2_b1_profile():
    score, label, _ = assess_language_fit(
        make_job("Very good English and German B2 required for daily communication."),
        PROFILE,
    )
    assert label == "stretch"
    assert score < 60


def test_c1_or_native_german_is_german_heavy():
    score, label, _ = assess_language_fit(
        make_job("Fluent English and German C1 are mandatory."),
        PROFILE,
    )
    assert label == "german_heavy"
    assert score <= 20


def test_b2_can_be_allowed_by_profile():
    profile = {**PROFILE, "max_german_requirement": "b2"}
    score, label, _ = assess_language_fit(make_job("English required. German B2."), profile)
    assert label == "german_growth"
    assert score >= 70


def test_overall_score_uses_language_weight():
    assert calculate_overall_score(80, 100, 35) == 87


def test_german_ad_with_english_working_language_is_recognized():
    score, label, reasons = assess_language_fit(
        make_job("Arbeitssprache Englisch. Deutschkenntnisse auf B1 Niveau. Sprachkurs möglich."), PROFILE
    )
    assert label == "german_growth"
    assert score >= 90
    assert any("English" in reason for reason in reasons)


def test_b1_requirement_is_a_stretch_for_an_a2_only_profile():
    profile = {**PROFILE, "max_german_requirement": "a2"}
    score, label, reasons = assess_language_fit(make_job("Deutschkenntnisse auf B1 Niveau erforderlich."), profile)
    assert label == "stretch"
    assert score < 60
    assert any("exceeds" in reason for reason in reasons)


def test_explicit_english_b2_does_not_become_a_german_b2_requirement():
    score, label, _ = assess_language_fit(make_job("Arbeitssprache Englisch. English B2 required."), PROFILE)
    assert label == "english_first"
    assert score >= 90


def test_no_german_requirement_is_treated_as_optional():
    score, label, reasons = assess_language_fit(
        make_job("Arbeitssprache Englisch; keine Deutschkenntnisse erforderlich."), PROFILE
    )
    assert label == "german_growth"
    assert score >= 90
    assert any("optional" in reason for reason in reasons)
