from app.employment_filter import assess_employment_fit
from app.providers import PROVIDERS
from app.source_catalog import SOURCE_CATALOG, render_search_url
from app.stepstone_provider import build_stepstone_search_url, parse_stepstone_search_html


def _part_time_profile():
    return {
        "name": "Werkstudent / Part-time",
        "slug": "werkstudent",
        "keywords": {"format": {"werkstudent": 10, "teilzeit": 8}},
    }


def test_stepstone_search_url_is_slugged_and_paginated():
    assert build_stepstone_search_url("Working Student Supply Chain", "Berlin") == (
        "https://www.stepstone.de/jobs/working-student-supply-chain/in-berlin"
    )
    assert build_stepstone_search_url("Teilzeit Einkauf", "Berlin Brandenburg", 2).endswith(
        "/jobs/teilzeit-einkauf/in-berlin-brandenburg?page=2"
    )


def test_stepstone_parser_preserves_employment_signal_for_strict_filter():
    html = """
    <html><body>
      <article data-at="job-item">
        <a href="/stellenangebote--Working-Student-Supply-Chain-Berlin-Example-GmbH--14221204-inline.html">
          Working Student Supply Chain (m/f/d)
        </a>
        <div data-at="job-item-company-name">Example GmbH</div>
        <div data-at="job-item-location">Berlin</div>
        <div data-at="job-item-description">Support planning, procurement and logistics reporting.</div>
        <div data-at="job-item-job-type">Teilzeit · 20 Stunden pro Woche</div>
        <div data-at="job-item-date">vor 1 Tag</div>
        <span>Teilweise Home-Office</span>
      </article>
    </body></html>
    """
    jobs = parse_stepstone_search_html(html)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "14221204"
    assert job.company == "Example GmbH"
    assert job.location == "Berlin"
    assert "Teilzeit" in job.description
    assert "20 Stunden pro Woche" in job.description
    assert job.remote is True
    ok, label, _ = assess_employment_fit(job, _part_time_profile())
    assert ok is True
    assert label == "part_time"


def test_stepstone_parser_fallback_reads_visible_card_lines():
    html = """
    <div class="result-card">
      <a href="https://www.stepstone.de/stellenangebote--Werkstudent-Logistik-Potsdam-ACME--998877-inline.html">Werkstudent Logistik</a>
      <span>ACME GmbH</span><span>Potsdam</span><span>Minijob / Teilzeit</span>
      <p>Unterstützung des Teams bei Planung, Disposition und operativen Logistikaufgaben.</p>
      <span>vor 3 Tagen</span>
    </div>
    """
    jobs = parse_stepstone_search_html(html)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "ACME GmbH"
    assert job.location == "Potsdam"
    assert "Minijob / Teilzeit" in job.description
    assert job.created_at == "vor 3 Tagen"


def test_stepstone_provider_registered_and_catalog_has_manual_fallback():
    assert "stepstone" in PROVIDERS
    automatic = next(x for x in SOURCE_CATALOG if x["key"] == "stepstone")
    fallback = next(x for x in SOURCE_CATALOG if x["key"] == "stepstone-search")
    assert automatic["source_type"] == "stepstone"
    assert automatic["mode"] == "experimental"
    assert fallback["source_type"] == "search_link"
    assert render_search_url(fallback["url_template"], "Werkstudent Supply Chain", "Berlin") == (
        "https://www.stepstone.de/jobs/werkstudent-supply-chain/in-berlin"
    )
