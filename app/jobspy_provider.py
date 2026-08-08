import asyncio
import hashlib
from datetime import date, datetime

from jobspy import scrape_jobs

from .models import Job
from . import providers


def _stable_id(*parts: str) -> str:
    return hashlib.sha256('|'.join(str(p or '') for p in parts).encode('utf-8')).hexdigest()[:24]


def _text(value) -> str:
    if value is None:
        return ''
    try:
        if value != value:  # pandas NaN
            return ''
    except Exception:
        pass
    return str(value)


def _date_text(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return _text(value)


def _scrape_one(term: str, source: dict, target_location: str):
    cfg = source.get('config', {})
    sites = cfg.get('sites') or ['linkedin', 'indeed', 'google']
    if isinstance(sites, str):
        sites = [s.strip() for s in sites.split(',') if s.strip()]
    supported = {'linkedin', 'indeed', 'google', 'glassdoor'}
    sites = [s for s in sites if s in supported]
    if not sites:
        raise RuntimeError('JobSpy has no supported sites enabled')

    wanted = max(1, min(int(cfg.get('results_per_term', 20)), 100))
    hours_old = max(1, min(int(cfg.get('hours_old', 168)), 24 * 30))
    fetch_linkedin_description = bool(cfg.get('linkedin_fetch_description', False))

    kwargs = {
        'site_name': sites,
        'search_term': term,
        'location': target_location,
        'results_wanted': wanted,
        'hours_old': hours_old,
        'country_indeed': 'Germany',
        'linkedin_fetch_description': fetch_linkedin_description,
    }
    if 'google' in sites:
        kwargs['google_search_term'] = f'{term} jobs near {target_location}'
    return scrape_jobs(**kwargs)


async def fetch_jobspy(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    cfg = source.get('config', {})
    max_terms = max(1, min(int(cfg.get('max_search_terms', 6)), 20))
    terms = [t for t in search_terms if t][:max_terms]
    if not terms:
        terms = ['working student supply chain']

    jobs: list[Job] = []
    seen: set[str] = set()
    for term in terms:
        frame = await asyncio.to_thread(_scrape_one, term, source, target_location)
        if frame is None or getattr(frame, 'empty', False):
            continue
        for _, row in frame.iterrows():
            site = _text(row.get('site')).lower() or 'jobspy'
            title = _text(row.get('title'))
            company = _text(row.get('company'))
            location = _text(row.get('location')) or target_location
            url = _text(row.get('job_url_direct')) or _text(row.get('job_url'))
            description = _text(row.get('description'))
            created = _date_text(row.get('date_posted'))
            external_id = _text(row.get('id')) or _stable_id(site, title, company, url)
            dedupe = f'{site}:{external_id}'
            if dedupe in seen:
                continue
            seen.add(dedupe)
            jobs.append(Job(
                source=f"{source['name']} / {site}",
                external_id=external_id,
                title=title,
                company=company,
                location=location,
                url=url,
                description=description,
                created_at=created,
                remote=bool(row.get('is_remote', False)),
            ))
    return jobs


# Register without coupling the stable provider module to this experimental dependency.
providers.PROVIDERS['jobspy'] = fetch_jobspy
