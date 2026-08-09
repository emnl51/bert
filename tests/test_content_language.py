from app import db
from app.content_language import detect_content_language
from app.models import Job


def test_detects_german_description_as_dominant():
    result = detect_content_language(
        "Process Engineer",
        "Wir suchen dich für unser Team. Du hast Erfahrung im Bereich Produktion und sehr gute Kenntnisse.",
    )

    assert result.code == "de"
    assert result.confidence >= 0.7


def test_detects_english_description_as_dominant():
    result = detect_content_language(
        "Prozessingenieur",
        "We are looking for you to join our team. Your experience and skills in production are important for this job.",
    )

    assert result.code == "en"
    assert result.confidence >= 0.7


def test_detects_bilingual_content_and_short_unknown_text():
    mixed = detect_content_language(
        "Engineer / Ingenieur",
        "We are an international company and you will work with our team. Wir sind ein internationales Unternehmen und du arbeitest mit unserem Team.",
    )

    assert mixed.code == "mixed"
    assert detect_content_language("Engineer", "Berlin").code == "unknown"


def test_manual_language_survives_job_refresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    job = Job(
        source="test",
        external_id="1",
        title="Engineer",
        company="Example",
        location="Berlin",
        url="https://example.test/1",
        description="We are looking for you to join our company and work with our international team.",
    )
    db.upsert_job(job)
    assert db.set_job_content_language(job.key, "de")["content_language_source"] == "manual"

    job.description = "We are looking for you to join our team with your skills and experience."
    db.upsert_job(job)

    with db.connection() as con:
        row = con.execute(
            "SELECT content_language,content_language_source FROM jobs WHERE job_key=?", (job.key,)
        ).fetchone()
    assert dict(row) == {"content_language": "de", "content_language_source": "manual"}


def test_auto_restores_detection_after_manual_override(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    job = Job(
        source="test",
        external_id="2",
        title="Engineer",
        company="Example",
        location="Berlin",
        url="https://example.test/2",
        description="We are looking for you to join our company and work with our international team.",
    )
    db.upsert_job(job)
    db.set_job_content_language(job.key, "de")

    result = db.set_job_content_language(job.key, "auto")

    assert result["content_language"] == "en"
    assert result["content_language_source"] == "detected"
