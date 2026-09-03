import re

from .models import Job
from .search_intent import ROLE_FAMILIES, ROLE_QUERY_TERMS, role_families_for_terms
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

STUDENT_SIGNALS = (
    "werkstudent",
    "working student",
    "student assistant",
    "studentische aushilfe",
    "studentische hilfskraft",
)
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


def profile_targets_full_time(profile: dict) -> bool:
    slug = _norm(profile.get("slug", ""))
    name = _norm(profile.get("name", ""))
    format_terms = _profile_format_terms(profile)
    identity = f"{slug} {name}"
    if any(x in identity for x in ("full-time", "full time", "vollzeit")):
        return True
    return any(term in FULL_TIME_SIGNALS for term in format_terms)


QUERY_ARRANGEMENT_PATTERN = re.compile(
    r"(?i)\b(?:werkstudent\w*|working student|student assistant|studentische(?:r|n)? \w+|"
    r"teilzeit|part[ -]?time|full[ -]?time|vollzeit|minijob|mini-job|geringf(?:ü|ue)gig\w*)\b"
)


def _base_provider_query(value: str, profile: dict) -> str:
    """Remove scheduling/location constraints that unnecessarily narrow discovery."""
    query = QUERY_ARRANGEMENT_PATTERN.sub(" ", _norm(value))
    locations = [profile.get("target_location", ""), *(profile.get("location_terms") or [])]
    for location in sorted({_norm(x) for x in locations if _norm(x)}, key=len, reverse=True):
        query = re.sub(rf"(?<!\w){re.escape(location)}(?!\w)", " ", query)
    return re.sub(r"\s+", " ", query).strip(" ,-/")


def search_terms_for_profile(profile: dict, configured_terms: list[str] | None = None) -> list[str]:
    """Plan balanced provider queries for one profile.

    Unqualified role queries are intentionally placed before schedule-specific variants.
    Providers such as JobSpy and StepStone cap the number of phrases they execute; the
    previous ordering spent that budget on several part-time spellings of the first role
    and never searched later role families.
    """
    keywords = profile.get("keywords") or {}
    raw_configured = configured_terms if configured_terms is not None else list((keywords.get("search") or {}).keys())
    configured = [str(term).strip() for term in raw_configured if str(term).strip()]
    title_terms = list((keywords.get("title") or {}).keys())
    intent_terms = configured if configured_terms is not None else [*title_terms, *configured]
    requested_families = role_families_for_terms(intent_terms)
    student_targeted = _profile_targets_students(profile)
    if (
        student_targeted
        and not profile_targets_full_time(profile)
        and requested_families in ([], ["logistics"], ["procurement", "logistics"])
    ):
        priority = [
            "werkstudent supply chain",
            "part time supply chain",
            "minijob logistik",
            "working student supply chain",
            "teilzeit supply chain",
            "werkstudent procurement",
        ]
        return list(dict.fromkeys([*priority, *configured]))

    base_configured = list(
        dict.fromkeys(term for value in configured if (term := _base_provider_query(value, profile)))
    )
    generated: list[str] = []
    covered_families: set[str] = set()

    # Keep the first configured phrase for each family and every unknown/custom role.
    # Repeated synonyms from one family move behind this coverage pass instead of
    # consuming the provider's complete query budget.
    for query in base_configured:
        families = role_families_for_terms([query])
        if not families or any(family not in covered_families for family in families):
            generated.append(query)
            covered_families.update(families)
    for family in requested_families:
        if family not in covered_families:
            generated.append(ROLE_QUERY_TERMS.get(family, ROLE_FAMILIES[family][:2])[0])
            covered_families.add(family)

    # Add the other language, then any remaining user phrases, before narrower
    # part-time variants. This preserves user intent without starving later roles.
    for family in requested_families:
        for query in ROLE_QUERY_TERMS.get(family, ROLE_FAMILIES[family][:2]):
            if query not in generated:
                generated.append(query)
    generated.extend(base_configured)
    generated.extend(configured)
    if profile_targets_part_time(profile) and not profile_targets_full_time(profile):
        for family in requested_families:
            english, german = ROLE_QUERY_TERMS.get(family, ROLE_FAMILIES[family][:2])
            generated.extend((f"{german} teilzeit", f"{english} part time", f"{german} minijob"))
    if not generated:
        generated.extend(title_terms)
    return list(dict.fromkeys(generated))


def _profile_targets_students(profile: dict) -> bool:
    keywords = profile.get("keywords") or {}
    terms = [profile.get("name", ""), profile.get("slug", ""), *list((keywords.get("format") or {}).keys())]
    return any(contains_affirmed_phrase(_norm(str(term)), signal) for term in terms for signal in STUDENT_SIGNALS)


def _weekly_hours(text: str) -> int | None:
    values = [int(match.group("high") or match.group("low")) for match in HOURS_PATTERN.finditer(text)]
    return min(values) if values else None


def assess_employment_fit(job: Job, profile: dict, strict: bool = True) -> tuple[bool, str, list[str]]:
    """Classify employment format, optionally enforcing it as a hard gate.

    A positive part-time/student signal wins over generic full-time boilerplate. For a
    strict part-time search, explicit full-time jobs and jobs with no confirmable target
    format are rejected. In preference mode they remain visible as stretch results.
    """
    targets_part_time = profile_targets_part_time(profile)
    targets_full_time = profile_targets_full_time(profile)
    title = _norm(job.title)
    body = _norm(f"{job.title} {job.description}")
    configured = _profile_format_terms(profile)
    student_only = any(contains_affirmed_phrase(body, term) for term in STUDENT_SIGNALS)

    # Student vacancies are a genuine eligibility constraint, independent of the
    # full-time/part-time preference selected on the profile.
    if student_only and not _profile_targets_students(profile):
        return False, "student_only", ["employment mismatch: enrolled student required"]
    if targets_part_time == targets_full_time:
        return True, "not_restricted", []

    part_time_terms = (
        tuple(dict.fromkeys((*configured, *PART_TIME_SIGNALS))) if targets_part_time else PART_TIME_SIGNALS
    )
    part_time_title = any(contains_affirmed_phrase(title, term) for term in part_time_terms)
    part_time = part_time_title or any(contains_affirmed_phrase(body, term) for term in part_time_terms)
    full_time = any(contains_affirmed_phrase(body, term) for term in FULL_TIME_SIGNALS)
    weekly_hours = _weekly_hours(body)
    workload_match = WORKLOAD_PATTERN.search(body)
    workload = int(workload_match.group(1) or workload_match.group(2)) if workload_match else None
    if weekly_hours is not None and weekly_hours <= 32:
        part_time = True
    if workload is not None and workload <= 80:
        part_time = True
    if weekly_hours is not None and weekly_hours >= 35 and not part_time:
        full_time = True
    if workload is not None and workload >= 90 and not part_time:
        full_time = True

    if targets_part_time and part_time:
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
    if targets_part_time and full_time:
        reasons = ["employment mismatch: full-time"]
        return (not strict), "full_time", reasons
    if targets_part_time:
        reasons = ["employment mismatch: part-time/minijob not confirmed"]
        return (not strict), "unclear", reasons

    if full_time:
        return True, "full_time", ["employment: full-time confirmed"]
    if part_time:
        reasons = ["employment mismatch: part-time/student"]
        return (not strict), "part_time", reasons
    return (not strict), "unclear", ["employment mismatch: full-time not confirmed"]
