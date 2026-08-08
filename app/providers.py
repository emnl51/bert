import hashlib
import re
from urllib.parse import urlencode
import feedparser
import httpx
from .models import Job
from .source_catalog import render_search_url
from .stepstone_provider import fetch_stepstone


def _stable_id(*parts: str) -> str:
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:24]


def _safe_provider_error(source: dict, exc: Exception) -> str:
    text = str(exc)
    for value in (source.get('secrets') or {}).values():
        if value:
            text = text.replace(str(value), '***')
    text = re.sub(r'(?i)(api[_-]?key|token|secret|password)=([^&\s]+)', r'\1=***', text)
    text = re.sub(r'(https?://jooble\.org/api/)[^\s\'\"]+', r'\1***', text)
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status:
        return f'HTTP {status}: {getattr(exc, "response", None).reason_phrase or "request failed"}'
    return text[:500]


async def fetch_arbeitnow(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    pages = max(1, min(int(source.get('config', {}).get('pages', 5)), 20))
    jobs: list[Job] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            response = await client.get('https://www.arbeitnow.com/api/job-board-api', params={'page': page}, headers={'User-Agent': 'JobTrack/5.0'})
            response.raise_for_status()
            for item in response.json().get('data', []):
                title=item.get('title') or ''; company=item.get('company_name') or item.get('company') or ''; location=item.get('location') or ''; url=item.get('url') or ''
                jobs.append(Job(source=source['name'], external_id=str(item.get('slug') or item.get('id') or _stable_id(title,company,url)), title=title, company=company, location=location, url=url, description=item.get('description') or '', created_at=str(item.get('created_at') or ''), remote=bool(item.get('remote',False))))
    return jobs


async def fetch_adzuna(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    secrets=source.get('secrets',{}); app_id,app_key=secrets.get('app_id',''),secrets.get('app_key','')
    if not app_id or not app_key: raise RuntimeError('Adzuna credentials are not configured')
    config=source.get('config',{}); results_per_term=max(1,min(int(config.get('results_per_term',50)),50)); distance_km=max(1,min(int(config.get('distance_km',40)),200))
    jobs=[]; seen=set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms:
            params={'app_id':app_id,'app_key':app_key,'results_per_page':results_per_term,'what':term,'where':target_location,'distance':distance_km,'sort_by':'date','content-type':'application/json'}
            response=await client.get('https://api.adzuna.com/v1/api/jobs/de/search/1?'+urlencode(params),headers={'Accept':'application/json'}); response.raise_for_status()
            for item in response.json().get('results',[]):
                external_id=str(item.get('id') or _stable_id(item.get('title',''),item.get('redirect_url','')))
                if external_id in seen: continue
                seen.add(external_id); jobs.append(Job(source=source['name'],external_id=external_id,title=item.get('title') or '',company=(item.get('company') or {}).get('display_name',''),location=(item.get('location') or {}).get('display_name',''),url=item.get('redirect_url') or '',description=item.get('description') or '',created_at=item.get('created') or '',remote=False))
    return jobs


async def fetch_rss(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    config=source.get('config',{}); url=config.get('url','').strip()
    if not url: raise RuntimeError('RSS/Atom URL is empty')
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response=await client.get(url,headers={'User-Agent':'JobTrack/5.0'}); response.raise_for_status()
    parsed=feedparser.parse(response.content); jobs=[]
    for entry in parsed.entries[:200]:
        title=entry.get('title',''); link=entry.get('link',''); description=entry.get('summary','') or entry.get('description',''); company=entry.get('author','') or source['name']; location=entry.get('location','') or config.get('default_location',''); external=entry.get('id','') or entry.get('guid','') or _stable_id(title,company,link)
        jobs.append(Job(source=source['name'],external_id=str(external),title=title,company=company,location=location,url=link,description=description,created_at=entry.get('published','') or entry.get('updated',''),remote=False))
    return jobs


async def fetch_search_link(source: dict, search_terms: list[str], target_location: str) -> list[Job]: return []


async def fetch_jooble(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    api_key=source.get('secrets',{}).get('api_key','')
    if not api_key: raise RuntimeError('Jooble API key is not configured')
    config=source.get('config',{}); radius=str(config.get('radius',40)); result_count=max(1,min(int(config.get('results_per_term',20)),50)); jobs=[]; seen=set()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in search_terms:
            response=await client.post(f'https://jooble.org/api/{api_key}',json={'keywords':term,'location':target_location,'radius':radius,'ResultOnPage':result_count},headers={'Content-Type':'application/json','User-Agent':'JobTrack/5.0'}); response.raise_for_status()
            for item in response.json().get('jobs',[]):
                url=item.get('link') or ''; external_id=str(item.get('id') or _stable_id(item.get('title',''),item.get('company',''),url))
                if external_id in seen: continue
                seen.add(external_id); jobs.append(Job(source=source['name'],external_id=external_id,title=item.get('title') or '',company=item.get('company') or '',location=item.get('location') or target_location,url=url,description=item.get('snippet') or '',created_at=item.get('updated') or '',remote=False))
    return jobs


async def fetch_greenhouse(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    token=source.get('config',{}).get('board_token','').strip()
    if not token: raise RuntimeError('Greenhouse board token is missing')
    async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
        response=await client.get(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs',params={'content':'true'},headers={'User-Agent':'JobTrack/5.0'}); response.raise_for_status()
    return [Job(source=source['name'],external_id=str(i.get('id') or _stable_id(i.get('title',''),i.get('absolute_url',''))),title=i.get('title') or '',company=source.get('config',{}).get('company_name',token),location=(i.get('location') or {}).get('name',''),url=i.get('absolute_url') or '',description=i.get('content') or '',created_at=i.get('updated_at') or '',remote='remote' in ((i.get('location') or {}).get('name','').lower())) for i in response.json().get('jobs',[])]


async def fetch_lever(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    site=source.get('config',{}).get('site','').strip()
    if not site: raise RuntimeError('Lever site slug is missing')
    async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
        response=await client.get(f'https://api.lever.co/v0/postings/{site}',params={'mode':'json'},headers={'User-Agent':'JobTrack/5.0'}); response.raise_for_status()
    jobs=[]
    for item in response.json():
        loc=(item.get('categories') or {}).get('location') or ''; lists=item.get('lists') or []; description=' '.join([item.get('descriptionPlain') or '',*[(x.get('text') or '')+' '+(x.get('content') or '') for x in lists]])
        jobs.append(Job(source=source['name'],external_id=str(item.get('id') or _stable_id(item.get('text',''),item.get('hostedUrl',''))),title=item.get('text') or '',company=source.get('config',{}).get('company_name',site),location=loc,url=item.get('hostedUrl') or item.get('applyUrl') or '',description=description,created_at=str(item.get('createdAt') or ''),remote='remote' in loc.lower()))
    return jobs


async def fetch_smartrecruiters(source: dict, search_terms: list[str], target_location: str) -> list[Job]:
    company=source.get('config',{}).get('company_identifier','').strip()
    if not company: raise RuntimeError('SmartRecruiters company identifier is missing')
    base=f'https://api.smartrecruiters.com/v1/companies/{company}/postings'; jobs=[]; offset=0
    async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
        while offset<300:
            response=await client.get(base,params={'limit':100,'offset':offset},headers={'User-Agent':'JobTrack/5.0'}); response.raise_for_status(); data=response.json(); content=data.get('content',[])
            for item in content:
                loc_obj=item.get('location') or {}; loc=', '.join(str(loc_obj.get(k) or '') for k in ('city','region','country') if loc_obj.get(k)); job_url=item.get('ref') or item.get('applyUrl') or ''; job_ad=item.get('jobAd') if isinstance(item.get('jobAd'),dict) else {}; description=(((job_ad.get('sections') or {}).get('jobDescription') or {}).get('text') or '')
                jobs.append(Job(source=source['name'],external_id=str(item.get('id') or item.get('uuid') or _stable_id(item.get('name',''),job_url)),title=item.get('name') or item.get('title') or '',company=source.get('config',{}).get('company_name',company),location=loc,url=job_url,description=description,created_at=item.get('releasedDate') or '',remote='remote' in loc.lower()))
            offset+=len(content)
            if not content or offset>=int(data.get('totalFound') or 0): break
    return jobs


PROVIDERS={'arbeitnow':fetch_arbeitnow,'adzuna':fetch_adzuna,'rss':fetch_rss,'search_link':fetch_search_link,'jooble':fetch_jooble,'greenhouse':fetch_greenhouse,'lever':fetch_lever,'smartrecruiters':fetch_smartrecruiters,'stepstone':fetch_stepstone}


async def fetch_all_jobs(sources:list[dict],search_terms:list[str],target_location:str)->tuple[list[Job],list[str]]:
    jobs=[]; errors=[]
    for source in sources:
        provider=PROVIDERS.get(source['source_type'])
        if not provider:
            errors.append(f"{source['name']}: unsupported source type {source['source_type']}"); continue
        try: jobs.extend(await provider(source,search_terms,target_location))
        except Exception as exc: errors.append(f"{source['name']}: {_safe_provider_error(source,exc)}")
    if errors and not jobs: raise RuntimeError('; '.join(errors))
    return jobs,errors


async def test_source(source:dict,search_terms:list[str],target_location:str)->dict:
    provider=PROVIDERS.get(source['source_type'])
    if not provider: raise RuntimeError('Unsupported source type')
    test_copy={**source,'config':dict(source.get('config',{}))}
    if source['source_type']=='arbeitnow': test_copy['config']['pages']=1
    if source['source_type']=='adzuna': test_copy['config']['results_per_term']=min(5,int(test_copy['config'].get('results_per_term',5))); search_terms=search_terms[:1]
    if source['source_type']=='stepstone':
        test_copy['config'].update({'max_search_terms':1,'pages_per_term':1,'results_per_term':min(10,int(test_copy['config'].get('results_per_term',10)))})
        search_terms=search_terms[:1]
    if source['source_type']=='search_link':
        query=search_terms[0] if search_terms else 'jobs'; template=source.get('config',{}).get('url_template','')
        return {'ok':True,'count':0,'mode':'search-only','search_url':render_search_url(template,query,target_location) if template else ''}
    try: jobs=await provider(test_copy,search_terms[:2],target_location)
    except Exception as exc: raise RuntimeError(_safe_provider_error(source,exc)) from None
    return {'ok':True,'count':len(jobs),'sample':[{'title':j.title,'company':j.company,'location':j.location} for j in jobs[:3]]}
