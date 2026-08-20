from app.providers import _description_with_metadata


def test_provider_metadata_keeps_employment_schedule_and_role_tags():
    description = _description_with_metadata(
        "Qualitätsprüfung und Dokumentation.",
        employment_type=["part_time", "minijob"],
        working_hours="20 Stunden pro Woche",
        role_tags=["quality control", "production"],
    )
    assert "Employment Type: part_time, minijob" in description
    assert "Working Hours: 20 Stunden pro Woche" in description
    assert "Role Tags: quality control, production" in description
    assert description.endswith("Qualitätsprüfung und Dokumentation.")


def test_empty_provider_metadata_does_not_change_job_description():
    result = _description_with_metadata("Original description", employment_type=None, role_tags=[])
    assert result == "Original description"
