import hashlib
from urllib.parse import urlencode
import feedparser
import httpx
from .models import Job


def _stable_id(*parts: str) -> str:
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:24]


async def fetch_arbeitnow(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    pages = max(1, min(int(source.get('config', {}).get('pages', 5)), 20))
    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            response = await client.get(
                'https://www.arbeitnow.com/api/job-board-api',
                params={'page': page},
                headers={'User-Agent': 'BerlinSupplyChainTracker/3.0'},
            )
            response.raise_for_status()
            for item in response.json().get('data', []):
                title = item.get('title') or ''
                company = item.get('company_name') or item.get('company') or ''
                location = item.get('location') or ''
                url = item.get('url') or ''
                jobs.append(Job(
                    source=source['name'],
                    external_id=str(item.get('slug') or item.get('id') or _stable_id(title, company, url)),
                    title=title, company=company, location=location, url=url,
                    description=item.get('description') or '', created_at=str(item.get('created_at') or ''),
                    remote=bool(item.get('remote', False)),
                ))
    return jobs


async def fetch_adzuna(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    secrets = source.get('secrets', {})
    app_id, app_key = secrets.get('app_id', ''), secrets.get('app_key', '')
    if not app_id or not app_key:
        raise RuntimeError('Adzuna credentials are not configured')
    config = source.get('config', {})
    results_per_term = max(1, min(int(config.get('results_per_term', 50)), 50))
    distance_km = max(1, min(int(config.get('distance_km', 40)), 200))
    jobs: list[Job] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms:
            params = {
                'app_id': app_id, 'app_key': app_key, 'results_per_page': results_per_term,
                'what': term, 'where': target_location, 'distance': distance_km,
                'sort_by': 'date', 'content-type': 'application/json',
            }
            response = await client.get('https://api.adzuna.com/v1/api/jobs/de/search/1?' + urlencode(params), headers={'Accept': 'application/json'})
            response.raise_for_status()
            for item in response.json().get('results', []):
                external_id = str(item.get('id') or _stable_id(item.get('title', ''), item.get('redirect_url', '')))
                if external_id in seen:
                    continue
                seen.add(external_id)
                jobs.append(Job(
                    source=source['name'], external_id=external_id,
                    title=item.get('title') or '', company=(item.get('company') or {}).get('display_name', ''),
                    location=(item.get('location') or {}).get('display_name', ''), url=item.get('redirect_url') or '',
                    description=item.get('description') or '', created_at=item.get('created') or '', remote=False,
                ))
    return jobs


async def fetch_rss(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    config = source.get('config', {})
    url = config.get('url', '').strip()
    if not url:
        raise RuntimeError('RSS/Atom URL is empty')
    default_location = config.get('default_location', '')
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers={'User-Agent': 'BerlinSupplyChainTracker/3.0'})
        response.raise_for_status()
    parsed = feedparser.parse(response.content)
    jobs: list[Job] = []
    for entry in parsed.entries[:200]:
        title = entry.get('title', '')
        link = entry.get('link', '')
        description = entry.get('summary', '') or entry.get('description', '')
        company = entry.get('author', '') or source['name']
        location = entry.get('location', '') or default_location
        external = entry.get('id', '') or entry.get('guid', '') or _stable_id(title, company, link)
        jobs.append(Job(
            source=source['name'], external_id=str(external), title=title, company=company,
            location=location, url=link, description=description,
            created_at=entry.get('published', '') or entry.get('updated', ''), remote=False,
        ))
    return jobs


PROVIDERS = {'arbeitnow': fetch_arbeitnow, 'adzuna': fetch_adzuna, 'rss': fetch_rss}


async def fetch_all_jobs(sources: list[dict], search_terms: list[str], target_location: str) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    errors: list[str] = []
    for source in sources:
        provider = PROVIDERS.get(source['source_type'])
        if not provider:
            errors.append(f"{source['name']}: unsupported source type {source['source_type']}")
            continue
        try:
            jobs.extend(await provider(source, search_terms, target_location))
        except Exception as exc:
            errors.append(f"{source['name']}: {exc}")
    if errors and not jobs:
        raise RuntimeError('; '.join(errors))
    return jobs, errors


async def test_source(source: dict, search_terms: list[str], target_location: str) -> dict:
    provider = PROVIDERS.get(source['source_type'])
    if not provider:
        raise RuntimeError('Unsupported source type')
    # Reduce test load where possible.
    test_copy = {**source, 'config': dict(source.get('config', {}))}
    if source['source_type'] == 'arbeitnow':
        test_copy['config']['pages'] = 1
    if source['source_type'] == 'adzuna':
        test_copy['config']['results_per_term'] = min(5, int(test_copy['config'].get('results_per_term', 5)))
        search_terms = search_terms[:1]
    jobs = await provider(test_copy, search_terms[:2], target_location)
    return {'ok': True, 'count': len(jobs), 'sample': [{'title': j.title, 'company': j.company, 'location': j.location} for j in jobs[:3]]}
