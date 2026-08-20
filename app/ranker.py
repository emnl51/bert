import re

from .models import Job
from .search_intent import matched_role_families, role_families_for_terms
from .text_match import contains_affirmed_phrase, contains_phrase, normalize_text


def _normalise(value: str) -> str:
    return normalize_text(value)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(contains_phrase(text, phrase) for phrase in phrases)


def blocklist_matches(job: Job, keywords: dict[str, dict[str, int]]) -> list[str]:
    """Return configured hard-block terms found in the vacancy text."""
    body = _normalise(f"{job.title} {job.description}")
    matches = []
    for value in (keywords.get("blocklist") or {}).keys():
        term = _normalise(str(value))
        if term and contains_affirmed_phrase(body, term) and term not in matches:
            matches.append(term)
    return matches


def score_job(job: Job, keywords: dict[str, dict[str, int]], location_terms: list[str]) -> tuple[int, list[str]]:
    """Return a 0-100 role/skill fit score, independent from language fit."""
    title = _normalise(job.title)
    body = _normalise(f"{job.title} {job.description}")
    location = _normalise(job.location)
    score = 0
    reasons: list[str] = []

    for term, weight in keywords.get("title", {}).items():
        if contains_affirmed_phrase(title, term):
            score += weight
            reasons.append(f"title: {term}")
    requested_families = role_families_for_terms((keywords.get("title") or {}).keys())
    for family in matched_role_families(title, requested_families):
        if not any(reason.startswith("title:") for reason in reasons):
            score += 20
        reasons.append(f"role family: {family}")
    for term, weight in keywords.get("format", {}).items():
        if contains_affirmed_phrase(body, term):
            score += weight
            reasons.append(f"format: {term}")
    for term, weight in keywords.get("skill", {}).items():
        if contains_affirmed_phrase(body, term):
            score += weight
            if len(reasons) < 8:
                reasons.append(f"skill: {term}")
    for value, weight in (keywords.get("allowlist") or {}).items():
        term = _normalise(str(value))
        boost = max(0, int(weight))
        if term and contains_affirmed_phrase(body, term) and boost:
            score += boost
            if len(reasons) < 8:
                reasons.append(f"allowlist: {term}")
    for term, penalty in keywords.get("negative", {}).items():
        if contains_affirmed_phrase(title, term):
            score += penalty
            reasons.append(f"penalty: {term}")

    if location_terms and any(contains_phrase(location, area) for area in location_terms):
        score += 12
        reasons.append("target area")
    if job.remote:
        score += 3
    format_terms = keywords.get("format", {})
    if format_terms and not any(contains_phrase(body, term) for term in format_terms):
        score -= 8
    return min(max(score, 0), 100), reasons


ENGLISH_SIGNALS = (
    "fluent english",
    "business english",
    "excellent english",
    "very good english",
    "english required",
    "english is required",
    "working language is english",
    "english-speaking",
    "english speaking",
    "professional english",
    "strong english",
    "good command of english",
    "good knowledge of english",
    "international team",
    "international environment",
    "global team",
    "gute englischkenntnisse",
    "sehr gute englischkenntnisse",
    "arbeitssprache englisch",
    "englisch in wort und schrift",
)
GERMAN_OPTIONAL = (
    "german is a plus",
    "german would be a plus",
    "german is an advantage",
    "german preferred",
    "german nice to have",
    "german is nice to have",
    "german not required",
    "german is not required",
    "no german required",
    "german beneficial",
    "deutschkenntnisse von vorteil",
    "deutsch von vorteil",
    "deutsch wünschenswert",
    "deutsch wuenschenswert",
    "deutschkenntnisse sind ein plus",
    "deutschkenntnisse sind von vorteil",
    "german skills are a plus",
    "knowledge of german is a plus",
    "kein deutsch erforderlich",
    "keine deutschkenntnisse erforderlich",
    "deutsch nicht erforderlich",
    "deutschkenntnisse nicht erforderlich",
)
GERMAN_LEARNING = (
    "willingness to learn german",
    "willing to learn german",
    "learn german",
    "bereitschaft deutsch zu lernen",
    "deutschkurs",
    "german classes",
    "german course",
    "language course",
    "sprachkurs",
    "deutsch lernen",
)
BASIC_GERMAN = (
    "basic german",
    "basic knowledge of german",
    "german a2",
    "a2 german",
    "deutsch a2",
    "grundkenntnisse deutsch",
    "grundkenntnisse in deutsch",
    "german b1",
    "b1 german",
    "deutsch b1",
    "b1-niveau",
    "b1 level",
    "german level b1",
    "einfache deutschkenntnisse",
    "deutschkenntnisse auf grundniveau",
)
B2_PREFERRED = (
    "b2 preferred",
    "b2 is a plus",
    "b2 would be a plus",
    "b2 nice to have",
    "deutsch b2 von vorteil",
    "german b2 preferred",
    "german b2 is a plus",
)
B2_SIGNALS = (
    "german b2",
    "b2 german",
    "deutsch b2",
    "b2-niveau",
    "b2 level",
    "german level b2",
)
GERMAN_HEAVY = (
    "native german",
    "german native",
    "german mother tongue",
    "mother tongue german",
    "german c1",
    "c1 german",
    "deutsch c1",
    "c1-niveau",
    "german c2",
    "c2 german",
    "deutsch c2",
    "business fluent german",
    "business-fluent german",
    "fluent german required",
    "german mandatory",
    "german is mandatory",
    "german is essential",
    "verhandlungssicheres deutsch",
    "verhandlungssicher deutsch",
    "deutsch zwingend erforderlich",
    "fließende deutschkenntnisse",
    "fliessende deutschkenntnisse",
    "deutsch in wort und schrift",
    "fließend deutsch",
    "fliessend deutsch",
)
GENERIC_GERMAN_REQUIRED = (
    "german required",
    "german is required",
    "good german required",
    "deutsch erforderlich",
    "gute deutschkenntnisse erforderlich",
    "sehr gute deutschkenntnisse",
)

GERMAN_LEVEL_PATTERN = re.compile(
    r"(?:deutsch(?:kenntnisse)?|german)(?:\s+(?:auf|at|level|niveau|kenntnisse|skills|mindestens|minimum)){0,3}"
    r"[\s:()-]*(a1|a2|b1|b2|c1|c2)"
    r"|(?<!\w)(a1|a2|b1|b2|c1|c2)[\s-]*(?:niveau|level)?\s*(?:deutsch(?:kenntnisse)?|german)",
    re.IGNORECASE,
)
LEVEL_RANK = {"a1": 1, "a2": 2, "a2_b1": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}


def _german_levels(text: str) -> list[str]:
    levels = []
    for match in GERMAN_LEVEL_PATTERN.finditer(text):
        phrase = match.group(0)
        if contains_affirmed_phrase(text, phrase):
            levels.append((match.group(1) or match.group(2)).lower())
    return levels


def assess_language_fit(job: Job, profile: dict) -> tuple[int, str, list[str]]:
    """Classify language requirements for an English-first A2/B1 German profile."""
    body = _normalise(f"{job.title} {job.description}")
    english = _has_any(body, ENGLISH_SIGNALS)
    german_optional = _has_any(body, GERMAN_OPTIONAL)
    german_learning = _has_any(body, GERMAN_LEARNING)
    explicit_levels = _german_levels(body)
    basic_german = _has_any(body, BASIC_GERMAN) or any(level in ("a1", "a2", "b1") for level in explicit_levels)
    b2_preferred = _has_any(body, B2_PREFERRED)
    b2 = any(contains_affirmed_phrase(body, phrase) for phrase in B2_SIGNALS) or "b2" in explicit_levels
    german_heavy = any(contains_affirmed_phrase(body, phrase) for phrase in GERMAN_HEAVY) or any(
        level in ("c1", "c2") for level in explicit_levels
    )
    generic_required = any(contains_affirmed_phrase(body, phrase) for phrase in GENERIC_GERMAN_REQUIRED)
    prefer_growth = bool(profile.get("prefer_german_growth", True))
    max_requirement = str(profile.get("max_german_requirement", "b1")).lower()
    max_rank = LEVEL_RANK.get(max_requirement, LEVEL_RANK["b1"])

    reasons: list[str] = []
    if english:
        reasons.append("English working environment")
    if german_optional:
        reasons.append("German optional / plus")
    if german_learning:
        reasons.append("German learning supported")
    if basic_german:
        reasons.append("A2/B1-compatible German")

    if german_heavy:
        reasons.append("C1/fluent/native German signal")
        return 15, "german_heavy", reasons

    highest_basic = max((LEVEL_RANK[level] for level in explicit_levels if level in LEVEL_RANK), default=0)
    if highest_basic and highest_basic > max_rank and highest_basic <= LEVEL_RANK["b1"]:
        reasons.append("German level exceeds configured maximum")
        return 52, "stretch", reasons

    if b2:
        if max_requirement == "b2":
            reasons.append("B2 within configured maximum")
            return (82 if english else 74), "german_growth", reasons
        if b2_preferred:
            reasons.append("B2 preferred, not mandatory")
            return 68, "stretch", reasons
        reasons.append("B2 German signal")
        return 42, "stretch", reasons

    if generic_required and not basic_german:
        reasons.append("German required, level unclear")
        return 48, "stretch", reasons

    if basic_german or german_optional or german_learning:
        score = 94 if english else 84
        if german_learning and prefer_growth:
            score = min(100, score + 4)
        return score, "german_growth", reasons

    if english:
        reasons.append("No mandatory German signal detected")
        return 92, "english_first", reasons

    reasons.append("Language requirement unclear")
    return 55, "unclear", reasons


def calculate_overall_score(job_score: int, language_score: int, language_weight: int = 35) -> int:
    language_weight = min(max(int(language_weight), 0), 100)
    role_weight = 100 - language_weight
    return round((job_score * role_weight + language_score * language_weight) / 100)
