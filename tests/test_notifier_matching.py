from app.models import Job
from app.notifier import build_text_digest


def test_digest_exposes_match_tier_for_constraint_review():
    job = Job(
        source="test",
        external_id="stretch",
        title="Process Engineer",
        company="Example",
        location="Berlin",
        url="https://example.com/stretch",
        score=82,
        language_score=92,
        overall_score=86,
        language_label="english_first",
    )
    job.match_tier = "stretch"
    assert "Match tier: Stretch" in build_text_digest([job])
