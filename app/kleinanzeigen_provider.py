import asyncio
import hashlib
import json
import re
import unicodedata
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from .models import Job

BASE_URL = "https://www.kleinanzeigen.de"
SEARCH_CATEGORY_ID = 102
_EMPLOYMENT_RE = re.compile(
    r"(?i)\b(teilzeit|vollzeit|mini[ -]?job|nebenjob|werkstudent\w*|"
    r"part[ -]?time|full[ -]?time|\d{1,2}\s*(?:stunden|std\.?|h)\s*(?:/|pro)\s*woche)\b"
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "jobs"


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


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
    delay = max(0.0, min(float(config.get("request_delay_seconds", 1.0)), 10.0))
    location = _clean(config.get("location_name") or target_location)
    location_id = str(config.get("location_id") or "").strip()
    terms = [_clean(term) for term in search_terms if _clean(term)][:max_terms]
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
                response = await client.get(build_kleinanzeigen_search_url(term, location, location_id, radius, page))
                if response.status_code in {403, 429}:
                    raise RuntimeError(
                        f"Kleinanzeigen blocked the request with HTTP {response.status_code}; source left experimental"
                    )
                response.raise_for_status()
                parsed = parse_kleinanzeigen_search_html(response.text, source.get("name") or "Kleinanzeigen Jobs")
                for job in parsed:
                    if job.external_id not in seen:
                        seen.add(job.external_id)
                        jobs.append(job)
                if not parsed:
                    if page == 1 and not jobs:
                        raise RuntimeError(
                            "Kleinanzeigen returned no parseable job cards; page layout or blocking may have changed"
                        )
                    break
                if delay:
                    await asyncio.sleep(delay)

        for job in jobs[:detail_limit]:
            try:
                response = await client.get(job.url)
                if response.status_code in {403, 429}:
                    break
                response.raise_for_status()
                detail = parse_kleinanzeigen_detail_html(response.text)
                if detail["description"]:
                    job.description = detail["description"]
                job.title = detail["title"] or job.title
                job.location = detail["location"] or job.location
                job.created_at = detail["created_at"] or job.created_at
            except (httpx.HTTPError, ValueError):
                continue
            if delay:
                await asyncio.sleep(delay)
    return jobs
