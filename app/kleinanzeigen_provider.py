import asyncio
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote, urljoin

import httpx
import tls_client
from bs4 import BeautifulSoup

from .models import Job

BASE_URL = "https://www.kleinanzeigen.de"
SEARCH_CATEGORY_ID = 102
_EMPLOYMENT_RE = re.compile(
    r"(?i)\b(teilzeit|vollzeit|mini[ -]?job|nebenjob|werkstudent\w*|"
    r"part[ -]?time|full[ -]?time|\d{1,2}\s*(?:stunden|std\.?|h)\s*(?:/|pro)\s*woche)\b"
)
_PART_TIME_RE = re.compile(r"(?i)\b(teilzeit|part[ -]?time|mini[ -]?job|nebenjob|werkstudent\w*)\b")
_FULL_TIME_RE = re.compile(r"(?i)\b(vollzeit|full[ -]?time)\b")
_BLOCK_PAGE_RE = re.compile(
    r"(?i)(captcha|access denied|verify (?:that )?you are human|unusual traffic|"
    r"bot detection|akamai|datadome|challenge-platform)"
)
_EMPTY_RESULT_RE = re.compile(r"(?i)(keine (?:anzeigen|ergebnisse|treffer)|0\s+ergebnisse)")
_INACTIVE_RE = re.compile(
    r"(?i)(anzeige ist nicht mehr verfügbar|anzeige wurde gelöscht|angebot ist nicht mehr verfügbar|"
    r"ad is no longer available)"
)
_ARRANGEMENTS = {"both", "full_time", "part_time"}
_QUERY_COVERAGE = {"focused", "balanced", "broad"}
_LOCALIZED_QUERIES = {
    "quality control": ("Qualitätsprüfer", "Qualitätskontrolle"),
    "quality inspector": ("Qualitätsprüfer", "Qualitätskontrolle"),
    "quality technician": ("Qualitätstechniker", "Qualitätsprüfer"),
    "quality engineer": ("Qualitätsingenieur", "Qualitätssicherung"),
    "production": ("Produktionsmitarbeiter", "Mitarbeiter Fertigung"),
    "production assistant": ("Produktionsassistenz", "Produktionsmitarbeiter"),
    "production planning": ("Arbeitsvorbereitung", "Produktionsplanung"),
    "process engineer": ("Prozessingenieur", "Prozesstechnik"),
    "technical office": ("Technische Sachbearbeitung", "Projektassistenz"),
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "jobs"


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _arrangement(value: str) -> str:
    value = _clean(value).lower()
    return value if value in _ARRANGEMENTS else "both"


def _query_for_arrangement(query: str, arrangement: str) -> str:
    query = _clean(query)
    if arrangement == "part_time" and not _PART_TIME_RE.search(query):
        return f"{query} Teilzeit"
    if arrangement == "full_time" and not _FULL_TIME_RE.search(query):
        return f"{query} Vollzeit"
    return query


def prepare_kleinanzeigen_search_terms(
    search_terms: list[str], arrangement: str, max_terms: int, coverage: str = "balanced"
) -> list[str]:
    """Create a bounded, profile-led set of Kleinanzeigen queries.

    Focused mode preserves profile phrases. Balanced mode adds one German market
    alias and full/part-time variants for generic phrases. Broad mode may use a
    second German alias while the source-level query budget remains authoritative.
    """
    coverage = _clean(coverage).lower()
    if coverage not in _QUERY_COVERAGE:
        coverage = "balanced"
    arrangement = _arrangement(arrangement)
    configured = list(dict.fromkeys(_clean(term) for term in search_terms if _clean(term)))
    batches: list[list[str]] = []
    for term in configured:
        explicit_format = bool(_PART_TIME_RE.search(term) or _FULL_TIME_RE.search(term))
        variants = [_query_for_arrangement(term, arrangement)]
        normalized = _clean(re.sub(_EMPLOYMENT_RE, "", term)).lower()
        aliases = _LOCALIZED_QUERIES.get(normalized, ())
        if coverage != "focused":
            variants.extend(_query_for_arrangement(alias, arrangement) for alias in aliases[:1])
            if arrangement == "both" and not explicit_format:
                variants.extend((f"{term} Vollzeit", f"{term} Teilzeit"))
                variants.extend(f"{alias} Vollzeit" for alias in aliases[:1])
                variants.extend(f"{alias} Teilzeit" for alias in aliases[:1])
            if coverage == "broad":
                variants.extend(_query_for_arrangement(alias, arrangement) for alias in aliases[1:2])
        batches.append(list(dict.fromkeys(_clean(value) for value in variants if _clean(value))))

    terms: list[str] = []
    for index in range(max((len(batch) for batch in batches), default=0)):
        for batch in batches:
            if index < len(batch) and batch[index] not in terms:
                terms.append(batch[index])
                if len(terms) >= max_terms:
                    return terms
    return terms


def _matches_arrangement(job: Job, arrangement: str) -> bool:
    if arrangement == "both":
        return True
    text = f"{job.title} {job.description}"
    part_time = bool(_PART_TIME_RE.search(text))
    full_time = bool(_FULL_TIME_RE.search(text))
    if arrangement == "part_time":
        return not (full_time and not part_time)
    return not (part_time and not full_time)


def _listing_date(value: str, today: date | None = None) -> date | None:
    today = today or datetime.now().date()
    value = _clean(value)
    if re.search(r"(?i)\bheute\b", value):
        return today
    if re.search(r"(?i)\bgestern\b", value):
        return today - timedelta(days=1)
    relative = re.search(r"(?i)vor\s+(\d+)\s+(tag|tagen|woche|wochen)", value)
    if relative:
        amount = int(relative.group(1)) * (7 if relative.group(2).lower().startswith("woche") else 1)
        return today - timedelta(days=amount)
    explicit = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", value)
    if explicit:
        try:
            return date(int(explicit.group(3)), int(explicit.group(2)), int(explicit.group(1)))
        except ValueError:
            return None
    return None


def _within_max_age(job: Job, max_age_days: int, today: date | None = None) -> bool:
    if max_age_days <= 0:
        return True
    published = _listing_date(job.created_at, today)
    return published is None or published >= (today or datetime.now().date()) - timedelta(days=max_age_days)


def _detail_priority(job: Job) -> tuple[int, int]:
    """Prioritize cards missing evidence needed by categorization and scoring."""
    text = f"{job.title} {job.description}"
    missing = sum(
        (
            len(_clean(job.description)) < 120,
            not _clean(job.company),
            not _clean(job.location),
            not _clean(job.created_at),
            not _EMPLOYMENT_RE.search(text),
        )
    )
    return (-missing, len(_clean(job.description)))


def _tls_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
    """Retry with browser-like TLS when a plain HTTP client receives a challenge page."""
    session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
    session.headers.update(headers)
    response = session.get(url, allow_redirects=True, timeout_seconds=30)
    return int(response.status_code), str(response.text or "")


async def _response_html(client: httpx.AsyncClient, url: str, headers: dict[str, str], *, detail: bool = False) -> str:
    response = await client.get(url)
    if response.status_code in {403, 429}:
        status, html = await asyncio.to_thread(_tls_get, url, headers)
        if status >= 400:
            raise RuntimeError(f"Kleinanzeigen blocked the request with HTTP {status}")
        return html
    response.raise_for_status()
    html = response.text
    parser = parse_kleinanzeigen_detail_html if detail else parse_kleinanzeigen_search_html
    parsed = parser(html)
    parseable = bool(parsed.get("description")) if detail else bool(parsed)
    if parseable or (not detail and _EMPTY_RESULT_RE.search(html)):
        return html
    status, fallback_html = await asyncio.to_thread(_tls_get, url, headers)
    if status >= 400:
        raise RuntimeError(f"Kleinanzeigen browser-compatible retry failed with HTTP {status}")
    return fallback_html


def build_kleinanzeigen_search_url(
    query: str,
    location: str = "",
    location_id: str = "",
    radius_km: int = 0,
    page: int = 1,
) -> str:
    query_slug = quote(_slug(query), safe="-")
    location_id = re.sub(r"\D", "", str(location_id or ""))
    page_part = f"seite:{int(page)}/" if int(page) > 1 else ""
    if location_id:
        location_slug = quote(_slug(location), safe="-")
        radius = max(0, min(int(radius_km or 0), 200))
        suffix = f"k0c{SEARCH_CATEGORY_ID}l{location_id}"
        if radius:
            suffix += f"r{radius}"
        return f"{BASE_URL}/s-jobs/{location_slug}/{page_part}{query_slug}/{suffix}"
    return f"{BASE_URL}/s-jobs/{page_part}{query_slug}/k0c{SEARCH_CATEGORY_ID}"


def _json_ld_descriptions(container) -> list[str]:
    descriptions: list[str] = []
    for script in container.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text() or "")
        except (TypeError, json.JSONDecodeError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            description = _clean(node.get("description"))
            if description:
                descriptions.append(description)
    return descriptions


def _card_company(card) -> str:
    company = (
        _clean(card.select_one(".aditem-main--bottom .text-module-oneline span").get_text(" "))
        if card.select_one(".aditem-main--bottom .text-module-oneline span")
        else ""
    )
    if company:
        return company
    shop = card.select_one('.aditem-main--bottom a[title^="Zum shop "]')
    return _clean(str(shop.get("title") or "").removeprefix("Zum shop ")) if shop else ""


def _description_with_signals(description: str, signal_text: str = "") -> str:
    signals = list(dict.fromkeys(match.group(0) for match in _EMPLOYMENT_RE.finditer(f"{signal_text} {description}")))
    if not signals:
        return description
    return f"Employment type: {'; '.join(signals[:6])}\n{description}".strip()


def parse_kleinanzeigen_search_html(html: str, source_name: str = "Kleinanzeigen Jobs") -> list[Job]:
    soup = BeautifulSoup(html or "", "html.parser")
    jobs: list[Job] = []
    seen: set[str] = set()
    for card in soup.select("#srchrslt-adtable article.aditem, article.aditem"):
        link = str(card.get("data-href") or "").strip()
        anchor = card.select_one(".aditem-main h2 a[href]") or card.select_one("a[href*='/s-anzeige/']")
        if not link and anchor:
            link = str(anchor.get("href") or "").strip()
        url = urljoin(BASE_URL, link)
        title = _clean(anchor.get_text(" ") if anchor else "")
        external_id = str(card.get("data-adid") or "").strip()
        if not external_id:
            match = re.search(r"/(\d+)-\d+-\d+(?:[/?#]|$)", link)
            external_id = match.group(1) if match else _stable_id(title, url)
        if not title or not link or external_id in seen:
            continue
        seen.add(external_id)

        location_node = card.select_one(".aditem-main--top--left")
        location = _clean(location_node.get_text(" ") if location_node else "")
        location = re.sub(r"\s*\(\d+(?:[.,]\d+)?\s*km\)\s*$", "", location, flags=re.I)
        created_node = card.select_one(".aditem-main--top--right")
        created_at = _clean(created_node.get_text(" ") if created_node else "")
        summary_node = card.select_one(".aditem-main--middle--description")
        summary = _clean(summary_node.get_text(" ") if summary_node else "")
        descriptions = _json_ld_descriptions(card)
        description = max([summary, *descriptions], key=len, default="")
        company = _card_company(card)
        combined = f"{title} {description}"
        jobs.append(
            Job(
                source=source_name,
                external_id=external_id,
                title=title,
                company=company,
                location=location,
                url=url,
                description=_description_with_signals(description, title),
                created_at=created_at,
                remote=bool(re.search(r"(?i)\b(homeoffice|remote|mobiles arbeiten)\b", combined)),
            )
        )
    return jobs


def parse_kleinanzeigen_detail_html(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    description_node = soup.select_one("#viewad-description-text")
    description = _clean(description_node.get_text(" ") if description_node else "")
    if not description:
        description = max(_json_ld_descriptions(soup), key=len, default="")
    attributes: list[str] = []
    for row in soup.select(".addetailslist--detail"):
        value_node = row.select_one(".addetailslist--detail--value")
        value = _clean(value_node.get_text(" ") if value_node else "")
        if not value:
            continue
        label_copy = BeautifulSoup(str(row), "html.parser")
        for node in label_copy.select(".addetailslist--detail--value"):
            node.decompose()
        label = _clean(label_copy.get_text(" "))
        if label:
            attributes.append(f"{label}: {value}")
    locality = soup.select_one("#viewad-locality")
    date_node = soup.select_one("#viewad-extra-info span")
    title_node = soup.select_one("#viewad-title")
    return {
        "title": _clean(title_node.get_text(" ") if title_node else ""),
        "location": _clean(locality.get_text(" ") if locality else ""),
        "created_at": _clean(date_node.get_text(" ") if date_node else ""),
        "description": _description_with_signals("\n".join([*attributes, description]).strip()),
    }


async def fetch_kleinanzeigen(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    config = source.get("config") or {}
    max_terms = max(1, min(int(config.get("max_search_terms", 6)), 20))
    pages = max(1, min(int(config.get("pages_per_term", 1)), 5))
    radius = max(0, min(int(config.get("radius_km", 40)), 200))
    detail_limit = max(0, min(int(config.get("detail_limit", 10)), 50))
    max_age_days = max(0, min(int(config.get("max_age_days", 30)), 365))
    delay = max(0.0, min(float(config.get("request_delay_seconds", 1.0)), 10.0))
    location = _clean(config.get("location_name") or target_location)
    location_id = str(config.get("location_id") or "").strip()
    arrangement = _arrangement(config.get("working_arrangement", "both"))
    coverage = str(config.get("query_coverage") or "balanced")
    terms = prepare_kleinanzeigen_search_terms(search_terms, arrangement, max_terms, coverage)
    if not terms:
        raise RuntimeError("Kleinanzeigen requires at least one profile-specific search phrase")

    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    }
    jobs: list[Job] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        for term in terms:
            for page in range(1, pages + 1):
                url = build_kleinanzeigen_search_url(term, location, location_id, radius, page)
                html = await _response_html(client, url, headers)
                parsed = parse_kleinanzeigen_search_html(html, source.get("name") or "Kleinanzeigen Jobs")
                for job in parsed:
                    if job.external_id not in seen:
                        seen.add(job.external_id)
                        jobs.append(job)
                if not parsed:
                    if page == 1 and not jobs and not _EMPTY_RESULT_RE.search(html):
                        page_kind = "an anti-bot page" if _BLOCK_PAGE_RE.search(html) else "unparseable HTML"
                        raise RuntimeError(f"Kleinanzeigen returned {page_kind} after a browser-compatible retry")
                    break
                if delay:
                    await asyncio.sleep(delay)

        inactive_ids: set[str] = set()
        detail_jobs = sorted(jobs, key=_detail_priority)[:detail_limit]
        for job in detail_jobs:
            try:
                html = await _response_html(client, job.url, headers, detail=True)
                if _INACTIVE_RE.search(html):
                    inactive_ids.add(job.external_id)
                    continue
                detail = parse_kleinanzeigen_detail_html(html)
                if detail["description"]:
                    job.description = detail["description"]
                job.title = detail["title"] or job.title
                job.location = detail["location"] or job.location
                job.created_at = detail["created_at"] or job.created_at
            except (httpx.HTTPError, RuntimeError, ValueError):
                continue
            if delay:
                await asyncio.sleep(delay)
    return [
        job
        for job in jobs
        if job.external_id not in inactive_ids
        and _within_max_age(job, max_age_days)
        and _matches_arrangement(job, arrangement)
    ]
