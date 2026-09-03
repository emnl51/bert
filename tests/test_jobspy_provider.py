import asyncio
import threading

from app import providers
from app import jobspy_provider
from app.source_catalog import SOURCE_CATALOG


class FakeFrame:
    empty = False

    def iterrows(self):
        rows = [
            {
                "site": "indeed",
                "id": "abc",
                "title": "Working Student Supply Chain",
                "company": "Example GmbH",
                "location": "Berlin",
                "job_url": "https://example.com/job/abc",
                "description": "English required. German is a plus.",
                "job_type": "parttime",
                "date_posted": "2026-08-08",
                "is_remote": False,
            },
            {
                "site": "linkedin",
                "id": "def",
                "title": "Werkstudent Procurement",
                "company": "Example AG",
                "location": "Berlin",
                "job_url": "https://example.com/job/def",
                "description": "International procurement team.",
                "job_type": "internship",
                "date_posted": "2026-08-07",
                "is_remote": False,
            },
        ]
        return iter(enumerate(rows))


def test_jobspy_registered_and_catalogued():
    assert providers.PROVIDERS["jobspy"] is jobspy_provider.fetch_jobspy
    item = next(x for x in SOURCE_CATALOG if x["key"] == "jobspy")
    assert item["source_type"] == "jobspy"
    assert item["mode"] == "experimental"


def test_jobspy_maps_rows(monkeypatch):
    # v13 isolates scraping per query and per site, so the scraper helper receives
    # the selected site explicitly.
    monkeypatch.setattr(jobspy_provider, "_scrape_one", lambda term, site, source, location: FakeFrame())
    source = {
        "name": "JobSpy Multi-board",
        "config": {"sites": ["linkedin", "indeed", "google"], "max_search_terms": 1},
    }
    jobs = asyncio.run(jobspy_provider.fetch_jobspy(source, ["supply chain"], "Berlin"))
    assert len(jobs) == 2
    assert jobs[0].title == "Working Student Supply Chain"
    assert jobs[0].source == "JobSpy Multi-board / indeed"
    assert "Employment type: parttime" in jobs[0].description
    assert jobs[1].source == "JobSpy Multi-board / linkedin"


def test_jobspy_site_failure_does_not_block_other_sites(monkeypatch):
    def fake_scrape(term, site, source, location):
        if site == "linkedin":
            raise RuntimeError("blocked")
        return FakeFrame()

    monkeypatch.setattr(jobspy_provider, "_scrape_one", fake_scrape)
    source = {
        "name": "JobSpy Multi-board",
        "config": {"sites": ["linkedin", "indeed"], "max_search_terms": 1},
    }
    jobs = asyncio.run(jobspy_provider.fetch_jobspy(source, ["supply chain"], "Berlin"))
    assert len(jobs) == 2
    assert any(job.source.endswith("/ indeed") for job in jobs)


def test_jobspy_starts_independent_board_workers_concurrently(monkeypatch):
    linkedin_started = threading.Event()
    indeed_started = threading.Event()

    def fake_scrape(term, site, source, location):
        if site == "linkedin":
            linkedin_started.set()
            assert indeed_started.wait(1), "Indeed was starved behind the LinkedIn worker"
        if site == "indeed":
            indeed_started.set()
        return FakeFrame()

    monkeypatch.setattr(jobspy_provider, "_scrape_one", fake_scrape)
    source = {
        "name": "JobSpy Multi-board",
        "config": {"sites": ["linkedin", "indeed"], "max_search_terms": 1},
    }
    jobs = asyncio.run(jobspy_provider.fetch_jobspy(source, ["process engineer"], "Berlin"))
    assert linkedin_started.is_set() and indeed_started.is_set()
    assert len(jobs) == 2
