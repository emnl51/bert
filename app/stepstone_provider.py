import asyncio
import hashlib
import re
import unicodedata
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import Job

BASE_URL = "https://www.stepstone.de"
_JOB_PATH = "/stellenangebote--"
_SKIP_LINES = {
    "gehalt anzeigen",
    "schnelle bewerbung",
    "anschreiben nicht erforderlich",
    "mehr",
    "neu",
}
_EMPLOYMENT_RE = re.compile(
    r"(?i)\b(werkstudent\w*|working student|studentische\w*|teilzeit|part[ -]?time|"
    r"minijob|mini-job|geringf(?:ü|ue)gig\w*|vollzeit|full[ -]?time|"
    r"\d{1,2}\s*(?:h|hours?|stunden)\s*(?:/|pro)\s*(?:week|woche))\b"
)
_POSTED_RE = re.compile(r"(?i)^(heute|gestern|vor\s+\d+\s+(?:stunde|stunden|tag|tagen|woche|wochen|monat|monaten))$")


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "jobs"


def build_stepstone_search_url(query: str, location: str, page: int = 1) -> str:
    url = f"{BASE_URL}/jobs/{_slug(query)}/in-{_slug(location)}"
    return url if page <= 1 else f"{url}?page={int(page)}"


def _data_at_text(container, needles: tuple[str, ...]) -> str:
    for node in container.find_all(attrs={"data-at": True}):
        marker = str(node.get("data-at") or "").lower()
        if any(needle in marker for needle in needles):
            text = _clean(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _job_container(anchor):
    node = anchor
    for _ in range(9):
        node = getattr(node, "parent", None)
        if node is None:
            break
        marker = str(node.get("data-at") or "").lower() if hasattr(node, "get") else ""
        if marker and ("job" in marker or "result" in marker):
            return node
        if getattr(node, "name", None) in {"article", "li"}:
            return node
        if hasattr(node, "find_all"):
            job_links = [x for x in node.find_all("a", href=True) if _JOB_PATH in str(x.get("href") or "")]
            text_len = len(_clean(node.get_text(" ", strip=True)))
            if len(job_links) == 1 and 60 <= text_len <= 6000:
                return node
    return anchor.parent


def _fallback_lines(container, title: str) -> list[str]:
    lines: list[str] = []
    for value in container.stripped_strings:
        text = _clean(value)
        if not text or text == title or text.lower() in _SKIP_LINES:
            continue
        if text not in lines:
            lines.append(text)
    return lines


def parse_stepstone_search_html(html: str, source_name: str = "StepStone Germany") -> list[Job]:
    soup = BeautifulSoup(html or "", "html.parser")
    jobs: list[Job] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        if _JOB_PATH not in href:
            continue
        title = _clean(anchor.get_text(" ", strip=True))
        if len(title) < 3:
            continue
        url = urljoin(BASE_URL, href.split("#", 1)[0])
        if url in seen:
            continue
        seen.add(url)

        container = _job_container(anchor)
        company = _data_at_text(container, ("company-name", "company_name", "job-company", "company"))
        location = _data_at_text(container, ("job-location", "location"))
        description = _data_at_text(container, ("job-description", "description", "snippet"))
        created_at = _data_at_text(container, ("date", "posted", "publication"))
        employment = _data_at_text(container, ("job-type", "employment", "contract"))

        lines = _fallback_lines(container, title)
        if not company and lines:
            company = lines[0]
        if not location and len(lines) > 1:
            location = lines[1]
        if not description:
            long_lines = [x for x in lines[2:] if len(x) >= 45]
            description = " ".join(long_lines[:3])

        employment_signals = []
        for line in lines:
            if _EMPLOYMENT_RE.search(line) and line not in employment_signals:
                employment_signals.append(line)
        if employment and employment not in employment_signals:
            employment_signals.insert(0, employment)
        if employment_signals:
            description = _clean(f"{description} StepStone employment: {'; '.join(employment_signals[:4])}")

        if not created_at:
            created_at = next((x for x in lines if _POSTED_RE.match(x)), "")

        external_match = re.search(r"--(\d+)(?:-|\b)", href)
        external_id = external_match.group(1) if external_match else _stable_id(title, company, url)
        container_text = _clean(container.get_text(" ", strip=True)).lower()
        remote = "home-office" in container_text or "remote" in container_text
        jobs.append(
            Job(
                source=source_name,
                external_id=str(external_id),
                title=title,
                company=company or "Unknown company",
                location=location,
                url=url,
                description=description,
                created_at=created_at,
                remote=remote,
            )
        )
    return jobs


async def fetch_stepstone(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    config = source.get("config") or {}
    max_terms = max(1, min(int(config.get("max_search_terms", 6)), 10))
    pages_per_term = max(1, min(int(config.get("pages_per_term", 1)), 3))
    results_per_term = max(1, min(int(config.get("results_per_term", 25)), 75))
    timeout_seconds = max(10, min(int(config.get("timeout_seconds", 30)), 90))
    request_delay = max(0.0, min(float(config.get("request_delay_seconds", 1.0)), 5.0))

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobTrack/16.3; +https://github.com/emnl51/jobtrack)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
    }
    all_jobs: list[Job] = []
    seen: set[str] = set()
    terms = [x.strip() for x in search_terms if str(x).strip()][:max_terms]
    if not terms:
        terms = ["werkstudent"]

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
        for term_index, term in enumerate(terms):
            term_count = 0
            for page in range(1, pages_per_term + 1):
                response = await client.get(build_stepstone_search_url(term, target_location, page))
                if response.status_code in {403, 429}:
                    raise RuntimeError(
                        f"StepStone blocked the request with HTTP {response.status_code}; source left experimental"
                    )
                response.raise_for_status()
                parsed = parse_stepstone_search_html(response.text, source.get("name") or "StepStone Germany")
                if not parsed:
                    if page == 1:
                        raise RuntimeError(
                            "StepStone returned no parseable job cards; page layout or rendering may have changed"
                        )
                    break
                for job in parsed:
                    job.discovered_queries = list(dict.fromkeys([*job.discovered_queries, term]))
                    if job.url in seen:
                        continue
                    seen.add(job.url)
                    all_jobs.append(job)
                    term_count += 1
                    if term_count >= results_per_term:
                        break
                if term_count >= results_per_term:
                    break
                if request_delay:
                    await asyncio.sleep(request_delay)
            if request_delay and term_index < len(terms) - 1:
                await asyncio.sleep(request_delay)

    return all_jobs
