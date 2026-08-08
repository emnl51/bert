from app.employment_filter import assess_employment_fit, search_terms_for_profile
from app.models import Job


PROFILE = {
    'name': 'Werkstudent / Part-time',
    'slug': 'werkstudent',
    'keywords': {
        'search': {
            'werkstudent supply chain': 0,
            'werkstudent procurement': 0,
        },
        'format': {
            'werkstudent': 34,
            'working student': 34,
            'teilzeit': 14,
            'part-time': 14,
            'part time': 14,
        },
    },
}


def job(title, description=''):
    return Job(
        source='test', external_id=title, title=title, company='Example GmbH',
        location='Berlin', url='https://example.com/job', description=description,
    )


def test_werkstudent_is_eligible():
    ok, label, reasons = assess_employment_fit(job('Werkstudent Supply Chain'), PROFILE)
    assert ok is True
    assert label == 'part_time'
    assert any('confirmed' in r for r in reasons)


def test_minijob_is_eligible_even_if_not_in_old_profile_json():
    ok, label, _ = assess_employment_fit(job('Logistik Minijob Berlin'), PROFILE)
    assert ok is True
    assert label == 'part_time'


def test_explicit_full_time_is_rejected():
    ok, label, reasons = assess_employment_fit(
        job('Supply Chain Specialist', 'Employment type: fulltime. Permanent position.'), PROFILE
    )
    assert ok is False
    assert label == 'full_time'
    assert 'employment mismatch: full-time' in reasons


def test_unknown_format_is_rejected_for_strict_part_time_profile():
    ok, label, reasons = assess_employment_fit(
        job('Supply Chain Specialist', 'International procurement and SAP responsibilities.'), PROFILE
    )
    assert ok is False
    assert label == 'unclear'
    assert any('not confirmed' in r for r in reasons)


def test_part_time_signal_wins_over_full_time_boilerplate():
    ok, label, _ = assess_employment_fit(
        job('Working Student Operations', 'This is a working student role. Our company also has full-time employees.'), PROFILE
    )
    assert ok is True
    assert label == 'part_time'


def test_part_time_search_terms_are_diversified_before_configured_terms():
    terms = search_terms_for_profile(PROFILE)
    assert terms[:3] == [
        'werkstudent supply chain',
        'part time supply chain',
        'minijob logistik',
    ]
    assert 'werkstudent procurement' in terms
    assert not any('manager berlin' in term for term in terms)
