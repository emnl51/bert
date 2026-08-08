from app.models import Job
from app.ranker import score_job

KEYWORDS = {
    'title': {'supply chain': 32, 'procurement': 30},
    'format': {'werkstudent': 30, 'working student': 30, 'teilzeit': 12},
    'skill': {'sap': 7, 'power bi': 6, 'supplier': 5},
    'negative': {'developer': -25},
    'search': {},
}
LOCATIONS = ['berlin', 'potsdam', 'hennigsdorf']


def test_good_werkstudent_match_scores_high():
    job = Job(
        source='test', external_id='1', title='Werkstudent Supply Chain',
        company='Example', location='Berlin', url='https://example.com',
        description='Support supplier projects using SAP and Power BI.',
    )
    score, reasons = score_job(job, KEYWORDS, LOCATIONS)
    assert score >= 80
    assert any('supply chain' in r for r in reasons)


def test_unrelated_role_scores_lower():
    job = Job(
        source='test', external_id='2', title='Software Developer',
        company='Example', location='Berlin', url='https://example.com',
        description='Full-time backend role.',
    )
    score, _ = score_job(job, KEYWORDS, LOCATIONS)
    assert score < 20
