"""Deterministic vacancy enrichment with evidence and confidence.

The matcher must distinguish "not found" from "does not match".  This module
extracts the small set of facts that can make a vacancy ineligible without
asking an LLM to invent missing details.
"""

from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup


_HOURS = re.compile(
    r"(?i)(?<!\d)(\d{1,2})(?:\s*(?:-|–|bis|to)\s*(\d{1,2}))?\s*"
    r"(?:stunden|std\.?|hours?|h|wochenstunden)(?:\s*(?:pro\s+woche|per\s+week|/\s*(?:woche|week)))?\b"
)
_WORKLOAD = re.compile(
    r"(?i)(?:teilzeit|part[ -]?time|pensum|workload|arbeitszeit)\s*[:(]?\s*(\d{1,3})\s*%"
    r"|(\d{1,3})\s*%\s*(?:stelle|pensum|workload|teilzeit)"
)
_EXPERIENCE = re.compile(
    r"(?i)(?<!\d)(\d{1,2})(?:\s*(?:-|–|bis|to)\s*(\d{1,2}))?\s*\+?\s*"
    r"(?:jahre?n?|years?)(?:\s+(?:berufs|professional|relevant|einschlägige\w*)?\s*erfahrung|\s+experience)"
)
_LANGUAGE_LEVEL = re.compile(
    r"(?i)\b(deutsch|german|englisch|english)(?:kenntnisse)?\s*(?:auf\s+)?(?:niveau\s*)?([abc][12])\b"
    r"|\b([abc][12])[- ]?(deutsch|german|englisch|english)(?:kenntnisse)?\b"
)
_STUDENT = re.compile(
    r"(?i)\b(immatrikuliert\w*|immatrikulation|enrolled\s+(?:at|in)|current(?:ly)?\s+enrolled|"
    r"werkstudent\w*|working student|studentische\w*)\b"
)
_FULL_TIME = re.compile(r"(?i)\b(vollzeit|full[ -]?time|fulltime|permanent full[ -]?time)\b")
_PART_TIME = re.compile(r"(?i)\b(teilzeit|part[ -]?time|minijob|werkstudent\w*|working student)\b")
_QUALITY_SPECIALIZATIONS = (
    (
        "quality_management",
        re.compile(
            r"(?i)\b(quality manager|head of quality|quality lead|qualitätsleiter\w*|qualitaetsleiter\w*|qualitätsmanager\w*)\b"
        ),
    ),
    (
        "quality_engineering",
        re.compile(r"(?i)\b(quality engineer|quality engineering|qualitätsingenieur\w*|qualitaetsingenieur\w*)\b"),
    ),
    (
        "quality_technician",
        re.compile(
            r"(?i)\b(quality technician|quality inspector|quality control technician|qualitätsprüfer\w*|"
            r"qualitaetspruefer\w*|prüftechniker\w*|prueftechniker\w*|qualitätstechniker\w*|"
            r"qualitaetstechniker\w*|wareneingangsprüfer\w*|wareneingangspruefer\w*|"
            r"mitarbeiter\w*\s+(?:in\s+der\s+)?qualität\w*)\b"
        ),
    ),
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def extract_job_facts(title: str, description: str, location: str = "") -> dict:
    """Extract eligibility facts and retain the exact supporting snippets."""
    text = _clean(f"{title}\n{description}")
    evidence: dict[str, list[str]] = {}

    hours = None
    hours_match = _HOURS.search(text)
    if hours_match:
        hours = int(hours_match.group(2) or hours_match.group(1))
        evidence["weekly_hours"] = [hours_match.group(0)]

    workload = None
    workload_match = _WORKLOAD.search(text)
    if workload_match:
        workload = int(workload_match.group(1) or workload_match.group(2))
        evidence["workload_pct"] = [workload_match.group(0)]

    part_time = (
        bool(_PART_TIME.search(text))
        or (hours is not None and hours <= 32)
        or (workload is not None and workload <= 80)
    )
    full_time = (
        bool(_FULL_TIME.search(text))
        or (hours is not None and hours >= 35)
        or (workload is not None and workload >= 90)
    )
    employment_type = "part_time" if part_time else "full_time" if full_time else "unknown"
    employment_match = _PART_TIME.search(text) if part_time else _FULL_TIME.search(text) if full_time else None
    if employment_match:
        evidence["employment_type"] = [employment_match.group(0)]

    experience_years = None
    experience_match = _EXPERIENCE.search(text)
    if experience_match:
        experience_years = int(experience_match.group(2) or experience_match.group(1))
        evidence["experience_years"] = [experience_match.group(0)]

    languages: dict[str, str] = {}
    for match in _LANGUAGE_LEVEL.finditer(text):
        language = (match.group(1) or match.group(4) or "").lower()
        level = (match.group(2) or match.group(3) or "").lower()
        key = "de" if language in {"deutsch", "german"} else "en"
        languages[key] = level
        evidence.setdefault(f"language_{key}", []).append(match.group(0))

    student_match = _STUDENT.search(text)
    student_required = bool(student_match)
    if student_match:
        evidence["student_required"] = [student_match.group(0)]

    specialization = ""
    for label, pattern in _QUALITY_SPECIALIZATIONS:
        match = pattern.search(_clean(title))
        if match:
            specialization = label
            evidence["role_specialization"] = [match.group(0)]
            break

    found = sum(
        value not in (None, "", {}, False, "unknown")
        for value in (hours, workload, employment_type, experience_years, languages, student_required, specialization)
    )
    return {
        "employment_type": employment_type,
        "weekly_hours": hours,
        "workload_pct": workload,
        "student_required": student_required,
        "experience_years": experience_years,
        "language_levels": languages,
        "role_specialization": specialization,
        "location": _clean(location),
        "confidence": "high" if found >= 3 else "medium" if found >= 1 else "unknown",
        "evidence": evidence,
    }


def _public_http_url(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTP(S) job URLs are supported")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except OSError as exc:
        raise ValueError("Job URL hostname could not be resolved") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Private or local job URLs are not allowed")
    return parsed.geturl()


def _jobposting_from_json(value):
    if isinstance(value, list):
        for item in value:
            found = _jobposting_from_json(item)
            if found:
                return found
    if isinstance(value, dict):
        kind = value.get("@type")
        if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
            return value
        return _jobposting_from_json(value.get("@graph", []))
    return None


async def fetch_public_job(url: str, *, max_bytes: int = 2_000_000) -> dict:
    """Fetch a public vacancy page, validating every redirect against SSRF."""
    current = await asyncio.to_thread(_public_http_url, url)
    headers = {"User-Agent": "BertJobAnalyzer/20 (+https://github.com/emnl51/bert)"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers=headers) as client:
        for _ in range(4):
            response = await client.get(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location", "")
                if not location:
                    raise ValueError("Job page redirect has no destination")
                current = await asyncio.to_thread(_public_http_url, urljoin(current, location))
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise ValueError("Job URL did not return an HTML page")
            if len(response.content) > max_bytes:
                raise ValueError("Job page is too large to analyze")
            soup = BeautifulSoup(response.text, "html.parser")
            posting = None
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    posting = _jobposting_from_json(json.loads(script.string or "null"))
                except (TypeError, json.JSONDecodeError):
                    continue
                if posting:
                    break
            posting = posting or {}
            organization = posting.get("hiringOrganization") or {}
            location = posting.get("jobLocation") or {}
            if isinstance(location, list):
                location = location[0] if location else {}
            address = location.get("address") if isinstance(location, dict) else {}
            if not isinstance(address, dict):
                address = {}
            description = _clean(BeautifulSoup(str(posting.get("description") or ""), "html.parser").get_text(" "))
            if not description:
                main = soup.select_one("main, article, [itemprop=description]") or soup.body
                description = _clean(main.get_text(" ", strip=True) if main else "")[:50_000]
            title = _clean(posting.get("title") or (soup.title.string if soup.title else ""))
            return {
                "url": current,
                "title": title,
                "company": _clean(organization.get("name") if isinstance(organization, dict) else ""),
                "location": _clean(
                    ", ".join(
                        str(address.get(key) or "")
                        for key in ("addressLocality", "addressRegion", "addressCountry")
                        if address.get(key)
                    )
                ),
                "description": description,
                "published_at": _clean(posting.get("datePosted")),
                "employment_type": posting.get("employmentType") or "",
            }
    raise ValueError("Too many redirects while fetching job page")


async def enrich_jobs(jobs: list, *, limit: int = 8, priority_terms: list[str] | None = None) -> dict:
    """Enrich only evidence-poor candidates with bounded concurrent requests."""
    candidates = [
        job
        for job in jobs
        if getattr(job, "url", "")
        and (urlsplit(str(getattr(job, "url", ""))).hostname or "").lower() not in {"example.com", "www.example.com"}
        and (
            len(str(getattr(job, "description", "") or "").split()) < 35
            or extract_job_facts(job.title, job.description, job.location)["employment_type"] == "unknown"
        )
    ]
    if priority_terms:
        intent_tokens = [set(_clean(term).lower().split()) for term in priority_terms if _clean(term)]

        def priority(job) -> float:
            title_tokens = set(_clean(getattr(job, "title", "")).lower().split())
            return max((len(title_tokens & terms) / len(terms) for terms in intent_tokens if terms), default=0.0)

        candidates.sort(key=priority, reverse=True)
    candidates = candidates[: max(0, min(int(limit), 20))]
    semaphore = asyncio.Semaphore(4)
    enriched = failed = 0

    async def enrich(job):
        nonlocal enriched, failed
        try:
            async with semaphore:
                detail = await fetch_public_job(job.url)
        except Exception:
            failed += 1
            job.enrichment_status = "unavailable"
            return
        description = str(detail.get("description") or "")
        if detail.get("employment_type"):
            description = f"Employment type: {detail['employment_type']}\n{description}".strip()
        if len(description) > len(str(job.description or "")):
            job.description = description
        for field in ("title", "company", "location", "created_at"):
            detail_key = "published_at" if field == "created_at" else field
            if not getattr(job, field, "") and detail.get(detail_key):
                setattr(job, field, str(detail[detail_key]))
        job.enrichment_status = "enriched"
        enriched += 1

    await asyncio.gather(*(enrich(job) for job in candidates))
    return {"attempted": len(candidates), "enriched": enriched, "failed": failed}
