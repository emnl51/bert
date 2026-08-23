"""Shared bilingual role intent for provider queries and vacancy matching."""

from .text_match import contains_affirmed_phrase, normalize_text


ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "quality": (
        "quality engineer",
        "quality assurance",
        "quality control",
        "quality inspection",
        "quality inspector",
        "quality assistant",
        "quality technician",
        "qualitätsingenieur",
        "qualitaetsingenieur",
        "qualitätssicherung",
        "qualitaetssicherung",
        "qualitätskontrolle",
        "qualitaetskontrolle",
        "qualitätsprüfung",
        "qualitaetspruefung",
        "qualitätsprüfer",
        "qualitaetspruefer",
        "wareneingangsprüfung",
    ),
    "production": (
        "production",
        "production assistant",
        "production support",
        "production coordinator",
        "production technician",
        "manufacturing assistant",
        "produktionsassistenz",
        "produktionsmitarbeiter",
        "produktionshelfer",
        "mitarbeiter produktion",
        "fertigungsmitarbeiter",
        "fertigungsassistenz",
        "produktion",
        "fertigung",
    ),
    "planning": (
        "production planner",
        "production planning",
        "production scheduling",
        "planning assistant",
        "material planning",
        "produktionsplanung",
        "produktionsplaner",
        "fertigungsplanung",
        "arbeitsvorbereitung",
        "disposition",
    ),
    "process": (
        "process engineer",
        "process engineering",
        "process optimization",
        "continuous improvement",
        "prozessingenieur",
        "prozessoptimierung",
        "prozessplanung",
        "prozesstechnik",
    ),
    "technical office": (
        "technical office",
        "technical assistant",
        "technical documentation",
        "office assistant",
        "administrative assistant",
        "project assistant",
        "technische sachbearbeitung",
        "sachbearbeitung",
        "projektassistenz",
        "dokumentation",
        "büroassistenz",
        "bueroassistenz",
    ),
    "procurement": (
        "procurement",
        "purchasing",
        "buyer",
        "purchasing assistant",
        "einkauf",
        "einkäufer",
        "einkaeufer",
    ),
    "logistics": (
        "supply chain",
        "logistics",
        "logistics coordinator",
        "logistik",
        "lieferkette",
        "supply chain assistant",
    ),
}


def role_families_for_terms(terms) -> list[str]:
    """Return only families explicitly requested by this profile."""
    requested = [normalize_text(str(term)) for term in terms if normalize_text(str(term))]
    return [
        family
        for family, aliases in ROLE_FAMILIES.items()
        if any(contains_affirmed_phrase(term, alias) for term in requested for alias in aliases)
    ]


def matched_role_families(text: str, requested_families: list[str]) -> list[str]:
    return [
        family
        for family in requested_families
        if any(contains_affirmed_phrase(text, alias) for alias in ROLE_FAMILIES.get(family, ()))
    ]
