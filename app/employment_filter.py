import re

from .models import Job
from .search_intent import ROLE_FAMILIES, role_families_for_terms
from .text_match import contains_affirmed_phrase


PART_TIME_SIGNALS = (
    "werkstudent",
    "working student",
    "student assistant",
    "studentische aushilfe",
    "studentische hilfskraft",
    "teilzeit",
    "part-time",
    "part time",
    "parttime",
    "minijob",
    "mini-job",
    "geringfügige beschäftigung",
    "geringfuegige beschaeftigung",
    "20 hours per week",
    "20 hours/week",
    "20h/week",
    "20 stunden pro woche",
    "part_time",
    "part-time employment",
    "geringfügig",
    "geringfuegig",
)

FULL_TIME_SIGNALS = (
    "full-time",
    "full time",
    "fulltime",
    "vollzeit",
    "40 hours per week",
    "40 hours/week",
    "40h/week",
    "40 stunden pro woche",
    "permanent full-time",
    "full_time",
)

STUDENT_SIGNALS = ("werkstudent", "working student", "student assistant", "studentische aushilfe")
HOURS_PATTERN = re.compile(
    r"(?<!\d)(?P<low>\d{1,2})(?:\s*(?:-|–|bis|to)\s*(?P<high>\d{1,2}))?"
    r"\s*(?:stunden|std\.?|hours?|h|wochenstunden)"
    r"(?:\s*(?:pro\s+woche|per\s+week|/\s*(?:woche|week)|weekly))?\b",
    re.IGNORECASE,
)
AFTERNOON_SIGNALS = (
    "nachmittags",
    "nachmittag",
    "afternoon",
    "spätschicht",
    "spaetschicht",
    "flexible working hours",
    "flexible arbeitszeiten",
)
AFTERNOON_TIME_PATTERN = re.compile(r"(?:ab|from)\s+(?:1[2-9]|2[0-1])(?:[:.]\d{2})?\s*(?:uhr|h)?\b")
WORKLOAD_PATTERN = re.compile(
    r"(?:teilzeit|part[ -]?time|pensum|workload|arbeitszeit)\s*[:(]?\s*(\d{1,3})\s*%"
    r"|(\d{1,3})\s*%\s*(?:stelle|pensum|workload|teilzeit)",
    re.IGNORECASE,
)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _profile_format_terms(profile: dict) -> tuple[str, ...]:
    raw = ((profile.get("keywords") or {}).get("format") or {}).keys()
    return tuple(_norm(x) for x in raw if _norm(x))


def profile_targets_part_time(profile: dict) -> bool:
    slug = _norm(profile.get("slug", ""))
    name = _norm(profile.get("name", ""))
    format_terms = _profile_format_terms(profile)
    identity = f"{slug} {name}"
    if any(x in identity for x in ("werkstudent", "part-time", "part time", "teilzeit", "minijob")):
        return True
    return any(term in PART_TIME_SIGNALS for term in format_terms)


def search_terms_for_profile(profile: dict) -> list[str]:
    """Return profile-specific provider queries without mixing other enabled profiles.

    The built-in Werkstudent/Part-time profile gets diversified broad queries first so
    low JobSpy max_search_terms values still cover student, part-time and minijob work.
    User-configured queries remain included afterwards.
    """
    keywords = profile.get("keywords") or {}
    configured = [str(term).strip() for term in (keywords.get("search") or {}) if str(term).strip()]
    if not profile_targets_part_time(profile):
        return list(dict.fromkeys(configured or list((keywords.get("title") or {}).keys())))

    title_terms = list((keywords.get("title") or {}).keys())
    requested_families = role_families_for_terms([*title_terms, *configured])
    student_targeted = _profile_targets_students(profile)
    if student_targeted and requested_families in ([], ["logistics"], ["procurement", "logistics"]):
        priority = [
            "werkstudent supply chain",
            "part time supply chain",
            "minijob logistik",
            "working student supply chain",
            "teilzeit supply chain",
            "werkstudent procurement",
        ]
        return list(dict.fromkeys([*priority, *configured]))

    generated = list(configured)
    query_batches = []
    preferred_german_roles = {
        "quality": "qualitätskontrolle",
        "production": "produktionsassistenz",
        "planning": "arbeitsvorbereitung",
        "process": "prozessoptimierung",
        "technical office": "technische sachbearbeitung",
        "procurement": "einkauf",
        "logistics": "logistik",
    }
    for family in requested_families:
        aliases = ROLE_FAMILIES[family]
        english = next((alias for alias in aliases if alias.isascii() and " " in alias), aliases[0])
        german = preferred_german_roles.get(family) or next((alias for alias in aliases if not alias.isascii()), "")
        queries = [f"{german or english} teilzeit", f"{english} part time"]
        if german:
            queries.append(f"{german} minijob")
        if student_targeted:
            queries.append(f"werkstudent {german or english}")
        query_batches.append(queries)
    for index in range(max((len(batch) for batch in query_batches), default=0)):
        generated.extend(batch[index] for batch in query_batches if index < len(batch))
    if not generated:
        generated.extend(f"{term} teilzeit" for term in title_terms)
    return list(dict.fromkeys(generated))


def _profile_targets_students(profile: dict) -> bool:
    keywords = profile.get("keywords") or {}
    terms = [profile.get("name", ""), profile.get("slug", ""), *list((keywords.get("format") or {}).keys())]
    return any(contains_affirmed_phrase(_norm(str(term)), signal) for term in terms for signal in STUDENT_SIGNALS)


def _weekly_hours(text: str) -> int | None:
    values = [int(match.group("high") or match.group("low")) for match in HOURS_PATTERN.finditer(text)]
    return min(values) if values else None


def assess_employment_fit(job: Job, profile: dict) -> tuple[bool, str, list[str]]:
    """Hard employment-format gate for profiles that explicitly target part-time work.

    A positive part-time/student signal wins over generic full-time boilerplate. For a
    strict part-time profile, explicit full-time jobs and jobs with no confirmable target
    format are not recommended. Other profiles keep the previous permissive behaviour.
    """
    if not profile_targets_part_time(profile):
        return True, "not_restricted", []

    title = _norm(job.title)
    body = _norm(f"{job.title} {job.description}")
    configured = _profile_format_terms(profile)

    positive_terms = tuple(dict.fromkeys((*configured, *PART_TIME_SIGNALS)))
    positive_title = any(contains_affirmed_phrase(title, term) for term in positive_terms)
    positive_body = positive_title or any(contains_affirmed_phrase(body, term) for term in positive_terms)
    full_time = any(contains_affirmed_phrase(body, term) for term in FULL_TIME_SIGNALS)
    weekly_hours = _weekly_hours(body)
    workload_match = WORKLOAD_PATTERN.search(body)
    workload = int(workload_match.group(1) or workload_match.group(2)) if workload_match else None
    student_only = any(contains_affirmed_phrase(title, term) for term in STUDENT_SIGNALS)

    if student_only and not _profile_targets_students(profile):
        return False, "student_only", ["employment mismatch: enrolled student required"]

    if weekly_hours is not None and weekly_hours <= 32:
        positive_body = True
    if workload is not None and workload <= 80:
        positive_body = True
    if weekly_hours is not None and weekly_hours >= 35 and not positive_body:
        full_time = True
    if workload is not None and workload >= 90 and not positive_body:
        full_time = True

    if positive_body:
        reasons = ["employment: part-time/student confirmed"]
        if weekly_hours is not None:
            reasons.append(f"schedule: {weekly_hours} hours/week")
        if workload is not None:
            reasons.append(f"schedule: {workload}% workload")
        if AFTERNOON_TIME_PATTERN.search(body) or any(
            contains_affirmed_phrase(body, signal) for signal in AFTERNOON_SIGNALS
        ):
            reasons.append("schedule: afternoon/flexible")
        return True, "part_time", reasons
    if full_time:
        return False, "full_time", ["employment mismatch: full-time"]
    return False, "unclear", ["employment mismatch: part-time/minijob not confirmed"]
