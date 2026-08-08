from urllib.parse import quote_plus

SOURCE_CATALOG = [
    {'key':'jobspy','name':'JobSpy — LinkedIn / Indeed / Google / Glassdoor','source_type':'jobspy','mode':'experimental','description':'Experimental open-source scraper integration for LinkedIn, Indeed, Google Jobs and Glassdoor. Disabled until explicitly configured; may be affected by rate limits or anti-bot changes.'},
    {'key':'linkedin','name':'LinkedIn Jobs','source_type':'search_link','mode':'search-only','description':'Open a targeted LinkedIn Jobs search. No scraping is performed by the stable JobTrack providers.','url_template':'https://www.linkedin.com/jobs/search/?keywords={query}&location={location}'},
    {'key':'indeed','name':'Indeed Germany','source_type':'search_link','mode':'search-only','description':'Open a targeted Indeed Germany search. No scraping is performed by the stable JobTrack providers.','url_template':'https://de.indeed.com/jobs?q={query}&l={location}'},
    {'key':'stepstone','name':'StepStone Germany','source_type':'search_link','mode':'search-only','description':'Open a StepStone search. JobTrack does not bypass site access controls.','url_template':'https://www.stepstone.de/jobs/{query}/in-{location}'},
    {'key':'google','name':'Google Jobs Search','source_type':'search_link','mode':'search-only','description':'Open Google job-oriented search results. Google Cloud Talent Solution is not a public Google Jobs feed.','url_template':'https://www.google.com/search?q={query}+jobs+{location}'},
    {'key':'glassdoor','name':'Glassdoor','source_type':'search_link','mode':'search-only','description':'Open a targeted Glassdoor search; no automated scraping in the stable provider layer.','url_template':'https://www.google.com/search?q=site%3Aglassdoor.de+{query}+{location}'},
    {'key':'talent','name':'Talent.com','source_type':'search_link','mode':'search-only','description':'Open a targeted Talent.com search; no automated scraping.','url_template':'https://de.talent.com/jobs?k={query}&l={location}'},
    {'key':'arbeitsagentur','name':'Bundesagentur für Arbeit','source_type':'search_link','mode':'search-only','description':'Open Bundesagentur Jobsuche in a new tab. Can later be replaced by an approved API integration.','url_template':'https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=1&was={query}&wo={location}'},
    {'key':'jooble','name':'Jooble API','source_type':'jooble','mode':'api','description':'Official REST API. Requires a Jooble API key.'},
    {'key':'greenhouse','name':'Greenhouse Job Board','source_type':'greenhouse','mode':'api','description':'Public Greenhouse Job Board API for a specific company board token.'},
    {'key':'lever','name':'Lever Postings','source_type':'lever','mode':'api','description':'Public postings feed for a specific Lever site/company slug.'},
    {'key':'smartrecruiters','name':'SmartRecruiters Postings','source_type':'smartrecruiters','mode':'api','description':'Public company postings endpoint using the SmartRecruiters company identifier.'},
    {'key':'rss','name':'Custom RSS / Atom','source_type':'rss','mode':'feed','description':'Add any standards-compliant jobs RSS or Atom feed.'},
]


def render_search_url(template: str, query: str, location: str) -> str:
    return template.format(query=quote_plus(query.strip()), location=quote_plus(location.strip()))
