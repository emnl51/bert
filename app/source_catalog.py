import re
import unicodedata
from urllib.parse import quote_plus

SOURCE_CATALOG = [
    {
        "key": "jobspy",
        "name": "JobSpy — LinkedIn / Indeed / Google / Glassdoor",
        "source_type": "jobspy",
        "mode": "experimental",
        "description": "Experimental open-source scraper integration for LinkedIn, Indeed, Google Jobs and Glassdoor. Disabled until explicitly configured; may be affected by rate limits or anti-bot changes.",
    },
    {
        "key": "stepstone",
        "name": "StepStone Germany — Experimental",
        "source_type": "stepstone",
        "mode": "experimental",
        "description": "Experimental direct StepStone search provider. Uses public job-search result pages with conservative request limits, no CAPTCHA/proxy bypass, and fails safely on blocking or layout changes.",
    },
    {
        "key": "kleinanzeigen",
        "name": "Kleinanzeigen Jobs — Experimental",
        "source_type": "kleinanzeigen",
        "mode": "experimental",
        "description": "Experimental provider for public Kleinanzeigen job listings. Uses conservative limits, optional detail enrichment, no CAPTCHA/proxy bypass, and fails safely if blocking or layout changes are detected.",
    },
    {
        "key": "linkedin",
        "name": "LinkedIn Jobs",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open a targeted LinkedIn Jobs search. No scraping is performed by the stable JobTrack providers.",
        "url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
    },
    {
        "key": "indeed",
        "name": "Indeed Germany",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open a targeted Indeed Germany search. No scraping is performed by the stable JobTrack providers.",
        "url_template": "https://de.indeed.com/jobs?q={query}&l={location}",
    },
    {
        "key": "stepstone-search",
        "name": "StepStone Germany — Manual search",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open the equivalent StepStone search in a new tab. Recommended as a fallback when the experimental provider is blocked or StepStone changes its page layout.",
        "url_template": "https://www.stepstone.de/jobs/{query_slug}/in-{location_slug}",
    },
    {
        "key": "google",
        "name": "Google Jobs Search",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open Google job-oriented search results. Google Cloud Talent Solution is not a public Google Jobs feed.",
        "url_template": "https://www.google.com/search?q={query}+jobs+{location}",
    },
    {
        "key": "glassdoor",
        "name": "Glassdoor",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open a targeted Glassdoor search; no automated scraping in the stable provider layer.",
        "url_template": "https://www.google.com/search?q=site%3Aglassdoor.de+{query}+{location}",
    },
    {
        "key": "talent",
        "name": "Talent.com",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open a targeted Talent.com search; no automated scraping.",
        "url_template": "https://de.talent.com/jobs?k={query}&l={location}",
    },
    {
        "key": "arbeitsagentur",
        "name": "Bundesagentur für Arbeit",
        "source_type": "search_link",
        "mode": "search-only",
        "description": "Open Bundesagentur Jobsuche in a new tab. Can later be replaced by an approved API integration.",
        "url_template": "https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=1&was={query}&wo={location}",
    },
    {
        "key": "jooble",
        "name": "Jooble API",
        "source_type": "jooble",
        "mode": "api",
        "description": "Official REST API. Requires a Jooble API key.",
    },
    {
        "key": "greenhouse",
        "name": "Greenhouse Job Board",
        "source_type": "greenhouse",
        "mode": "api",
        "description": "Public Greenhouse Job Board API for a specific company board token.",
    },
    {
        "key": "lever",
        "name": "Lever Postings",
        "source_type": "lever",
        "mode": "api",
        "description": "Public postings feed for a specific Lever site/company slug.",
    },
    {
        "key": "smartrecruiters",
        "name": "SmartRecruiters Postings",
        "source_type": "smartrecruiters",
        "mode": "api",
        "description": "Public company postings endpoint using the SmartRecruiters company identifier.",
    },
    {
        "key": "rss",
        "name": "Custom RSS / Atom",
        "source_type": "rss",
        "mode": "feed",
        "description": "Add any standards-compliant jobs RSS or Atom feed.",
    },
]


def _path_slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "jobs"


def render_search_url(template: str, query: str, location: str) -> str:
    return template.format(
        query=quote_plus(query.strip()),
        location=quote_plus(location.strip()),
        query_slug=_path_slug(query),
        location_slug=_path_slug(location),
    )
