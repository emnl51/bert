import re

from .models import Job


PART_TIME_SIGNALS = (
    'werkstudent', 'working student', 'student assistant', 'studentische aushilfe',
    'studentische hilfskraft', 'teilzeit', 'part-time', 'part time', 'parttime',
    'minijob', 'mini-job', 'geringfügige beschäftigung', 'geringfuegige beschaeftigung',
    '20 hours per week', '20 hours/week', '20h/week', '20 stunden pro woche',
)

FULL_TIME_SIGNALS = (
    'full-time', 'full time', 'fulltime', 'vollzeit', '40 hours per week',
    '40 hours/week', '40h/week', '40 stunden pro woche', 'permanent full-time',
)


def _norm(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').lower()).strip()


def _profile_format_terms(profile: dict) -> tuple[str, ...]:
    raw = ((profile.get('keywords') or {}).get('format') or {}).keys()
    return tuple(_norm(x) for x in raw if _norm(x))


def profile_targets_part_time(profile: dict) -> bool:
    slug = _norm(profile.get('slug', ''))
    name = _norm(profile.get('name', ''))
    format_terms = _profile_format_terms(profile)
    identity = f'{slug} {name}'
    if any(x in identity for x in ('werkstudent', 'part-time', 'part time', 'teilzeit', 'minijob')):
        return True
    return any(term in PART_TIME_SIGNALS for term in format_terms)


def search_terms_for_profile(profile: dict) -> list[str]:
    """Return profile-specific provider queries without mixing other enabled profiles.

    The built-in Werkstudent/Part-time profile gets diversified broad queries first so
    low JobSpy max_search_terms values still cover student, part-time and minijob work.
    User-configured queries remain included afterwards.
    """
    configured = list(((profile.get('keywords') or {}).get('search') or {}).keys())
    if not profile_targets_part_time(profile):
        return list(dict.fromkeys(configured))

    priority = [
        'werkstudent supply chain',
        'part time supply chain',
        'minijob logistik',
        'working student supply chain',
        'teilzeit supply chain',
        'werkstudent procurement',
    ]
    return list(dict.fromkeys([*priority, *configured]))


def assess_employment_fit(job: Job, profile: dict) -> tuple[bool, str, list[str]]:
    """Hard employment-format gate for profiles that explicitly target part-time work.

    A positive part-time/student signal wins over generic full-time boilerplate. For a
    strict part-time profile, explicit full-time jobs and jobs with no confirmable target
    format are not recommended. Other profiles keep the previous permissive behaviour.
    """
    if not profile_targets_part_time(profile):
        return True, 'not_restricted', []

    title = _norm(job.title)
    body = _norm(f'{job.title} {job.description}')
    configured = _profile_format_terms(profile)

    positive_terms = tuple(dict.fromkeys((*configured, *PART_TIME_SIGNALS)))
    positive_title = any(term in title for term in positive_terms)
    positive_body = positive_title or any(term in body for term in positive_terms)
    full_time = any(term in body for term in FULL_TIME_SIGNALS)

    if positive_body:
        return True, 'part_time', ['employment: part-time/student confirmed']
    if full_time:
        return False, 'full_time', ['employment mismatch: full-time']
    return False, 'unclear', ['employment mismatch: part-time/minijob not confirmed']
