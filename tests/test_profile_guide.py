from pathlib import Path


def test_profile_editor_has_guided_examples_and_bilingual_role_families():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    assert 'id="pfProfileGuide"' in text
    assert "technical_parttime" in text
    assert "quality_both" in text
    assert "engineering_fulltime" in text
    assert "office_minijob" in text
    assert "Qualitätskontrolle" in text
    assert "Arbeitsvorbereitung" in text
    assert "technical office" in text


def test_profile_guide_separates_work_type_student_eligibility_and_schedule():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    for field in ("pfGuideFormat-", "pfGuideEnrolled", "pfGuideHours", "pfGuideAvailability"):
        assert field in text
    assert "Working-student searches require current university enrollment." in text
    assert "Create separate full-time and part-time profiles" in text


def test_profile_guide_builds_provider_queries_and_checks_targeting_before_apply():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    assert "function buildProfileGuidePlan(selection)" in text
    assert "window.profileGuideBuildPlan=buildProfileGuidePlan" in text
    assert 'id="pfGuideQueryPreview"' in text
    assert 'id="pfGuideChecks"' in text
    assert "Add suggestions now" in text
    assert "keywords.language=" in text


def test_profile_guide_covers_german_and_english_proficiency():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    assert 'id="pfGuideGerman"' in text
    assert 'id="pfGuideEnglish"' in text
    assert 'id="pfGuideLanguageDe"' in text
    assert 'id="pfGuideLanguageEn"' in text
    assert 'value="b2">B2' in text
    assert 'value="c2">C2' in text


def test_profile_editor_persists_essentials_and_preserves_custom_terms():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    for field in (
        "current_english_level",
        "preferred_weekly_hours",
        "availability",
        "role_level",
        'id="pfGuideRoleLevel"',
        'id="pfAdvanced"',
    ):
        assert field in text
    assert "mergeGuideTerms" in text
    assert "existing custom terms were preserved" in text
    assert "if(guideDirty)applyProfileGuide(true)" in text


def test_quality_guide_distinguishes_technician_and_engineering_roles():
    text = Path("app/profile-ui.js").read_text(encoding="utf-8")
    assert "quality_technician" in text
    assert "quality_engineering" in text
    assert "Quality Technician" not in text  # aliases stay normalized/lowercase
    assert "Qualitätsprüfer" in text


def test_turkish_translations_cover_guided_profile_workflow():
    text = Path("app/ui-shell.js").read_text(encoding="utf-8")
    assert "Temel profil ayarları" in text
    assert "Mevcut İngilizce seviyeniz" in text
    assert "Öğleden sonra / 14.00 sonrası" in text
    assert "Önerileri şimdi ekle" in text


def test_both_search_paths_pass_profile_english_ability_into_matching():
    scheduled = Path("app/search_job_service.py").read_text(encoding="utf-8")
    legacy = Path("app/service.py").read_text(encoding="utf-8")
    assert '"current_english_level": profile_english_level(profile)' in scheduled
    assert '"current_english_level": profile_english_level(profile)' in legacy
