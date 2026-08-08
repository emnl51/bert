import asyncio
import hashlib
import logging
from datetime import date, datetime

from jobspy import scrape_jobs

from .models import Job
from . import providers

log = logging.getLogger('jobtrack.jobspy')


def _stable_id(*parts: str) -> str:
    return hashlib.sha256('|'.join(str(p or '') for p in parts).encode('utf-8')).hexdigest()[:24]


def _text(value) -> str:
    if value is None:
        return ''
    try:
        if value != value:
            return ''
    except Exception:
        pass
    return str(value)


def _date_text(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return _text(value)


def _scrape_one(term: str, site: str, source: dict, target_location: str):
    cfg = source.get('config', {})
    wanted = max(1, min(int(cfg.get('results_per_term', 20)), 100))
    hours_old = max(1, min(int(cfg.get('hours_old', 168)), 24 * 30))
    kwargs = {
        'site_name': [site], 'search_term': term, 'location': target_location,
        'results_wanted': wanted, 'hours_old': hours_old, 'country_indeed': 'Germany',
        'linkedin_fetch_description': bool(cfg.get('linkedin_fetch_description', False)) if site == 'linkedin' else False,
    }
    if site == 'google': kwargs['google_search_term'] = f'{term} jobs near {target_location}'
    return scrape_jobs(**kwargs)


async def fetch_jobspy(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    cfg = source.get('config', {})
    sites = cfg.get('sites') or ['linkedin', 'indeed', 'google']
    if isinstance(sites, str): sites = [s.strip() for s in sites.split(',') if s.strip()]
    supported = {'linkedin', 'indeed', 'google', 'glassdoor'}
    sites = [s for s in sites if s in supported]
    if not sites: raise RuntimeError('JobSpy has no supported sites enabled')

    max_terms = max(1, min(int(cfg.get('max_search_terms', 6)), 20))
    timeout_seconds = max(10, min(int(cfg.get('timeout_seconds', 60)), 180))
    total_timeout_seconds = max(30, min(int(cfg.get('total_timeout_seconds', 180)), 600))
    terms = [t for t in search_terms if t][:max_terms] or ['working student supply chain']

    jobs=[]; seen=set(); failures=[]
    loop = asyncio.get_running_loop(); started = loop.time()
    for term in terms:
        for site in sites:
            remaining = total_timeout_seconds - (loop.time() - started)
            if remaining <= 0:
                failures.append(f'provider total timeout after {total_timeout_seconds}s')
                log.warning('JobSpy total provider timeout reached after %ss', total_timeout_seconds)
                break
            call_timeout = max(1, min(timeout_seconds, int(remaining)))
            try:
                frame = await asyncio.wait_for(asyncio.to_thread(_scrape_one, term, site, source, target_location), timeout=call_timeout)
            except TimeoutError:
                failures.append(f'{site}: timeout after {call_timeout}s'); log.warning('JobSpy %s timed out after %ss for query %r', site, call_timeout, term); continue
            except Exception as exc:
                failures.append(f'{site}: {type(exc).__name__}'); log.warning('JobSpy %s failed for query %r: %s', site, term, type(exc).__name__); continue
            if frame is None or getattr(frame,'empty',False): continue
            for _,row in frame.iterrows():
                row_site=_text(row.get('site')).lower() or site
                title=_text(row.get('title'))
                company=_text(row.get('company'))
                location=_text(row.get('location')) or target_location
                url=_text(row.get('job_url_direct')) or _text(row.get('job_url'))
                description=_text(row.get('description'))
                # JobSpy exposes employment/job type on supported boards. Preserve it in
                # the scoring text so the employment-format gate can distinguish
                # FULL_TIME from PART_TIME even when the description is short.
                job_type=_text(row.get('job_type')) or _text(row.get('employment_type'))
                if job_type:
                    description=f'Employment type: {job_type}\n{description}'
                created=_date_text(row.get('date_posted'))
                external_id=_text(row.get('id')) or _stable_id(row_site,title,company,url)
                dedupe=f'{row_site}:{external_id}'
                if dedupe in seen: continue
                seen.add(dedupe)
                jobs.append(Job(source=f"{source['name']} / {row_site}",external_id=external_id,title=title,company=company,location=location,url=url,description=description,created_at=created,remote=bool(row.get('is_remote',False))))
        if loop.time() - started >= total_timeout_seconds: break
    if failures and not jobs: raise RuntimeError('JobSpy returned no jobs; '+', '.join(dict.fromkeys(failures)))
    return jobs


providers.PROVIDERS['jobspy'] = fetch_jobspy
