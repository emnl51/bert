import re
from datetime import date, datetime, timedelta, timezone

from .search_intent import ROLE_FAMILIES, matched_role_families


_PART_TIME_RE = re.compile(r"(?i)\b(teilzeit|part[ -]?time|nebenjob)\b")
_FULL_TIME_RE = re.compile(r"(?i)\b(vollzeit|full[ -]?time)\b")
_MINIJOB_RE = re.compile(r"(?i)\b(mini[ -]?job|geringfügig\w*|geringfuegig\w*)\b")
_STUDENT_RE = re.compile(r"(?i)\b(werkstudent\w*|working student|studentische hilfskraft|studentenjob|student job)\b")
_HOURS_RE = re.compile(
    r"(?i)(?<!\d)(\d{1,2})(?:\s*(?:-|–|bis|to)\s*(\d{1,2}))?\s*"
    r"(?:stunden|std\.?|hours?|h|wochenstunden)(?:\s*(?:pro\s+woche|per\s+week|/\s*woche))?\b"
)
_POSTAL_CODE_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")
_SHIFT_LABELS = (
    (re.compile(r"(?i)\b(3[ -]?schicht|dreischicht|three[ -]?shift)\b"), "Three-shift"),
    (re.compile(r"(?i)\b(2[ -]?schicht|zweischicht|two[ -]?shift)\b"), "Two-shift"),
    (re.compile(r"(?i)\b(nachtschicht|night shift)\b"), "Night shift"),
    (re.compile(r"(?i)\b(spätschicht|spaetschicht|late shift)\b"), "Late shift"),
    (re.compile(r"(?i)\b(frühschicht|fruehschicht|early shift)\b"), "Early shift"),
    (re.compile(r"(?i)\b(flexible arbeitszeit\w*|flexible working hours)\b"), "Flexible hours"),
)
_LEVEL_PATTERNS = (
    (re.compile(r"(?i)\b(?:\w*ingenieur\w*|engineer)\b"), "Engineer"),
    (re.compile(r"(?i)\b(?:\w*techniker\w*|technician)\b"), "Technician"),
    (re.compile(r"(?i)\b(?:\w*assistenz\w*|assistant|sachbearbeit\w*)\b"), "Assistant / office"),
    (re.compile(r"(?i)\b(?:\w*helfer\w*|operator|\w*mitarbeiter\w*)\b"), "Operator / employee"),
)
_CATEGORY_LABELS = {
    "quality": "Quality",
    "production": "Production",
    "planning": "Planning",
    "process": "Process engineering",
    "coating": "Paint / coating",
    "technical office": "Technical office",
    "procurement": "Procurement",
    "logistics": "Logistics",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _published_date(value: str, first_seen: str = "", today: date | None = None) -> date | None:
    today = today or datetime.now(timezone.utc).date()
    value = _clean(value)
    if re.search(r"(?i)\bheute\b", value):
        return today
    if re.search(r"(?i)\bgestern\b", value):
        return today - timedelta(days=1)
    relative = re.search(r"(?i)vor\s+(\d+)\s+(tag|tagen|woche|wochen)", value)
    if relative:
        multiplier = 7 if relative.group(2).lower().startswith("woche") else 1
        return today - timedelta(days=int(relative.group(1)) * multiplier)
    explicit = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", value)
    if explicit:
        try:
            return date(int(explicit.group(3)), int(explicit.group(2)), int(explicit.group(1)))
        except ValueError:
            return None
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            iso_date = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
            if iso_date:
                try:
                    return date.fromisoformat(iso_date.group(1))
                except ValueError:
                    return None
    if first_seen:
        try:
            return datetime.fromisoformat(first_seen.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _freshness(published: date | None, today: date) -> tuple[str, str, int | None]:
    if published is None:
        return "unknown", "Date unknown", None
    age = max(0, (today - published).days)
    if age == 0:
        return "today", "Today", age
    if age <= 7:
        return "week", f"{age}d old", age
    if age <= 30:
        return "month", f"{age}d old", age
    return "older", f"{age}d old", age


def classify_job_metadata(job: dict, today: date | None = None) -> dict:
    """Derive stable card metadata from provider content without external AI."""
    today = today or datetime.now(timezone.utc).date()
    title = _clean(job.get("title"))
    description = _clean(job.get("description"))
    text = f"{title} {description}"
    families = matched_role_families(text, list(ROLE_FAMILIES))
    categories = [_CATEGORY_LABELS[family] for family in families]
    if re.search(r"(?i)\b(production|produktion|fertigung|manufacturing)\b", text) and "Production" not in categories:
        categories.append("Production")

    if _STUDENT_RE.search(text):
        employment_type, employment_label = "working_student", "Working student"
    elif _MINIJOB_RE.search(text):
        employment_type, employment_label = "minijob", "Minijob"
    elif _PART_TIME_RE.search(text):
        employment_type, employment_label = "part_time", "Part-time"
    elif _FULL_TIME_RE.search(text):
        employment_type, employment_label = "full_time", "Full-time"
    else:
        employment_type, employment_label = "unknown", "Work time unknown"

    hours_match = _HOURS_RE.search(text)
    weekly_hours = int(hours_match.group(2) or hours_match.group(1)) if hours_match else None
    schedule = next((label for pattern, label in _SHIFT_LABELS if pattern.search(text)), "")
    level = next((label for pattern, label in _LEVEL_PATTERNS if pattern.search(title)), "Unspecified")
    location = _clean(job.get("location"))
    postal_match = _POSTAL_CODE_RE.search(location)
    published = _published_date(job.get("created_at", ""), job.get("first_seen", ""), today)
    freshness, freshness_label, age_days = _freshness(published, today)

    quality = 20
    quality += 25 if len(description) >= 120 else 10 if description else 0
    quality += 15 if _clean(job.get("company")) else 0
    quality += 15 if location else 0
    quality += 10 if published else 0
    quality += 10 if employment_type != "unknown" else 0
    quality += 5 if categories else 0

    return {
        "categories": categories or ["Other"],
        "primary_category": categories[0] if categories else "Other",
        "job_level": level,
        "employment_type": employment_type,
        "employment_label": employment_label,
        "weekly_hours": weekly_hours,
        "schedule_label": schedule,
        "postal_code": postal_match.group(1) if postal_match else "",
        "published_date": published.isoformat() if published else "",
        "age_days": age_days,
        "freshness": freshness,
        "freshness_label": freshness_label,
        "data_quality": min(100, quality),
        "description_preview": description[:260].rstrip(),
    }
