from datetime import date

from app.job_metadata import classify_job_metadata


def test_quality_technician_metadata_categorizes_work_time_location_and_freshness():
    metadata = classify_job_metadata(
        {
            "title": "Qualitätstechniker (m/w/d) Teilzeit",
            "company": "Example GmbH",
            "location": "13507 Berlin-Tegel",
            "created_at": "Gestern, 10:35",
            "first_seen": "2026-08-23T08:00:00+00:00",
            "description": (
                "Teilzeit mit 25 Stunden pro Woche. Durchführung von Qualitätskontrolle, "
                "SPC-Prüfungen und Dokumentation in der Produktion. Flexible Arbeitszeiten."
            ),
        },
        today=date(2026, 8, 23),
    )
    assert metadata["primary_category"] == "Quality"
    assert "Production" in metadata["categories"]
    assert metadata["job_level"] == "Technician"
    assert metadata["employment_type"] == "part_time"
    assert metadata["weekly_hours"] == 25
    assert metadata["schedule_label"] == "Flexible hours"
    assert metadata["postal_code"] == "13507"
    assert metadata["freshness"] == "week"
    assert metadata["age_days"] == 1
    assert metadata["data_quality"] == 100


def test_metadata_falls_back_to_first_seen_without_inventing_work_type():
    metadata = classify_job_metadata(
        {
            "title": "Technische Sachbearbeitung",
            "company": "",
            "location": "Berlin",
            "created_at": "Auf Anfrage",
            "first_seen": "2026-08-20T08:00:00+00:00",
            "description": "Dokumentation und Projektunterstützung.",
        },
        today=date(2026, 8, 23),
    )
    assert metadata["primary_category"] == "Technical office"
    assert metadata["employment_type"] == "unknown"
    assert metadata["published_date"] == "2026-08-20"
    assert metadata["freshness_label"] == "3d old"
    assert metadata["data_quality"] < 80


def test_metadata_prefers_iso_publication_date_over_first_seen():
    metadata = classify_job_metadata(
        {
            "title": "Mitarbeiter Qualitätskontrolle",
            "created_at": "2026-07-15T10:30:00Z",
            "first_seen": "2026-08-23T08:00:00+00:00",
            "description": "Kontrolle und Dokumentation in der Produktion.",
        },
        today=date(2026, 8, 23),
    )

    assert metadata["published_date"] == "2026-07-15"
    assert metadata["freshness"] == "older"
    assert metadata["age_days"] == 39


def test_job_review_cards_expose_actionable_categorized_metadata():
    text = open("app/review-ui.js", encoding="utf-8").read()
    for marker in (
        "primary_category",
        "employment_label",
        "schedule_label",
        "freshness_label",
        "description_preview",
        "data_quality",
        "published_date",
        "postal_code",
    ):
        assert marker in text


def test_kleinanzeigen_source_exposes_active_search_coverage_controls():
    text = open("app/source-ui.js", encoding="utf-8").read()
    assert "Search coverage" in text
    assert "Balanced · profile + German variants" in text
    assert "query_coverage" in text
    assert "Incomplete cards are enriched first" in text
