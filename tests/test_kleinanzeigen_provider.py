import asyncio
from datetime import date

import httpx

import app.kleinanzeigen_provider as kleinanzeigen_provider
from app.kleinanzeigen_provider import (
    build_kleinanzeigen_search_url,
    fetch_kleinanzeigen,
    parse_kleinanzeigen_detail_html,
    parse_kleinanzeigen_search_html,
    prepare_kleinanzeigen_search_terms,
)
from app.providers import PROVIDERS
from app.source_catalog import SOURCE_CATALOG


SEARCH_HTML = """
<ul id="srchrslt-adtable">
  <li class="ad-listitem">
    <article class="aditem" data-adid="3491213154"
      data-href="/s-anzeige/qualitaetspruefer/3491213154-109-9668">
      <div class="aditem-main">
        <div class="aditem-main--top">
          <div class="aditem-main--top--left">10115 Berlin - Mitte (2 km)</div>
          <div class="aditem-main--top--right">Gestern, 10:35</div>
        </div>
        <div class="aditem-main--middle">
          <h2><a href="/s-anzeige/qualitaetspruefer/3491213154-109-9668">Qualitätsprüfer (m/w/d) Teilzeit</a></h2>
          <p class="aditem-main--middle--description">Qualitätsprüfung in der Produktion, 25 Stunden pro Woche.</p>
        </div>
        <div class="aditem-main--bottom"><div class="text-module-oneline"><span>Example GmbH</span></div></div>
      </div>
    </article>
  </li>
</ul>
"""


DETAIL_HTML = """
<h1 id="viewad-title">Qualitätsprüfer (m/w/d) Teilzeit</h1>
<span id="viewad-locality">10115 Berlin - Mitte</span>
<div id="viewad-extra-info"><span>22.08.2026</span></div>
<div class="addetailslist">
  <li class="addetailslist--detail">Arbeitszeit<span class="addetailslist--detail--value">Teilzeit</span></li>
</div>
<p id="viewad-description-text">SPC-Prüfungen und Dokumentation in der Fertigung.</p>
"""


def test_kleinanzeigen_url_uses_jobs_category_location_radius_and_page():
    assert build_kleinanzeigen_search_url("Qualitätsprüfer", "Berlin", "3331", 40) == (
        "https://www.kleinanzeigen.de/s-jobs/berlin/qualitatsprufer/k0c102l3331r40"
    )
    assert "/berlin/seite:2/qualitatsprufer/" in build_kleinanzeigen_search_url(
        "Qualitätsprüfer", "Berlin", "3331", 40, 2
    )


def test_kleinanzeigen_search_parser_maps_job_and_employment_metadata():
    jobs = parse_kleinanzeigen_search_html(SEARCH_HTML)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.external_id == "3491213154"
    assert job.company == "Example GmbH"
    assert job.location == "10115 Berlin - Mitte"
    assert job._kleinanzeigen_distance_km == 2
    assert job.url.startswith("https://www.kleinanzeigen.de/s-anzeige/")
    assert "Employment type: Teilzeit; 25 Stunden pro Woche" in job.description


def test_kleinanzeigen_detail_parser_preserves_full_text_and_attributes():
    detail = parse_kleinanzeigen_detail_html(DETAIL_HTML)
    assert detail["created_at"] == "22.08.2026"
    assert detail["location"] == "10115 Berlin - Mitte"
    assert "Arbeitszeit: Teilzeit" in detail["description"]
    assert "SPC-Prüfungen" in detail["description"]


def test_kleinanzeigen_provider_registered_and_catalogued():
    assert "kleinanzeigen" in PROVIDERS
    item = next(entry for entry in SOURCE_CATALOG if entry["key"] == "kleinanzeigen")
    assert item["source_type"] == "kleinanzeigen"
    assert item["mode"] == "experimental"


def test_kleinanzeigen_fetch_deduplicates_queries_and_enriches_details(monkeypatch):
    calls = []
    for variable in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
        monkeypatch.delenv(variable, raising=False)

    async def fake_get(self, url, *args, **kwargs):
        calls.append(str(url))
        html = DETAIL_HTML if "/s-anzeige/" in str(url) else SEARCH_HTML
        return httpx.Response(200, text=html, request=httpx.Request("GET", str(url)))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    source = {
        "name": "Kleinanzeigen Jobs",
        "config": {
            "location_name": "Berlin",
            "location_id": "3331",
            "radius_km": 40,
            "max_search_terms": 2,
            "pages_per_term": 1,
            "detail_limit": 1,
            "request_delay_seconds": 0,
        },
    }
    jobs = asyncio.run(fetch_kleinanzeigen(source, ["Qualitätsprüfer", "Quality Inspector"], "Berlin"))
    assert len(jobs) == 1
    assert "SPC-Prüfungen" in jobs[0].description
    assert len(calls) == 3
    assert source["_provider_diagnostics"] == {
        "provider_raw": 2,
        "provider_duplicates": 1,
        "filtered_inactive": 0,
        "filtered_stale": 0,
        "filtered_arrangement": 0,
        "filtered_location": 0,
        "provider_accepted": 1,
    }


def test_kleinanzeigen_retries_challenge_page_with_browser_compatible_tls(monkeypatch):
    challenge = "<html><title>Access denied</title><p>Verify you are human</p></html>"
    for variable in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
        monkeypatch.delenv(variable, raising=False)

    async def fake_get(self, url, *args, **kwargs):
        return httpx.Response(200, text=challenge, request=httpx.Request("GET", str(url)))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(kleinanzeigen_provider, "_tls_get", lambda url, headers: (200, SEARCH_HTML))
    source = {
        "name": "Kleinanzeigen Jobs",
        "config": {"detail_limit": 0, "request_delay_seconds": 0},
    }
    jobs = asyncio.run(fetch_kleinanzeigen(source, ["Qualitätsprüfer"], "Berlin"))
    assert len(jobs) == 1


def test_kleinanzeigen_working_arrangement_targets_queries_and_filters_explicit_opposite(monkeypatch):
    calls = []
    for variable in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
        monkeypatch.delenv(variable, raising=False)

    async def fake_get(self, url, *args, **kwargs):
        calls.append(str(url))
        return httpx.Response(200, text=SEARCH_HTML, request=httpx.Request("GET", str(url)))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    source = {
        "name": "Kleinanzeigen Jobs",
        "config": {
            "working_arrangement": "full_time",
            "detail_limit": 0,
            "request_delay_seconds": 0,
        },
    }
    jobs = asyncio.run(fetch_kleinanzeigen(source, ["Qualitätsprüfer"], "Berlin"))
    assert jobs == []
    assert "qualitatsprufer-vollzeit" in calls[0]
    assert source["_provider_diagnostics"]["filtered_arrangement"] == 1
    assert source["_provider_diagnostics"]["provider_accepted"] == 0


def test_kleinanzeigen_source_ui_supports_both_full_and_part_time():
    text = open("app/source-ui.js", encoding="utf-8").read()
    assert "Full-time and part-time" in text
    assert "working_arrangement" in text
    assert "Incomplete cards are enriched first" in text
    assert "Last 7 days" in text
    assert "Last 30 days" in text
    assert "Bert verifies card distances" in text


def test_exact_city_location_filter_rejects_other_cities_and_accepts_berlin_districts():
    berlin_job = parse_kleinanzeigen_search_html(SEARCH_HTML)[0]
    potsdam_job = parse_kleinanzeigen_search_html(
        SEARCH_HTML.replace("10115 Berlin - Mitte (2 km)", "14467 Potsdam (28 km)")
    )[0]
    hamburg_job = parse_kleinanzeigen_search_html(
        SEARCH_HTML.replace("10115 Berlin - Mitte (2 km)", "20095 Hamburg (255 km)")
    )[0]

    assert kleinanzeigen_provider._matches_location(berlin_job, "Berlin", "3331", 0) is True
    assert kleinanzeigen_provider._matches_location(potsdam_job, "Berlin", "3331", 0) is False
    assert kleinanzeigen_provider._matches_location(potsdam_job, "Berlin", "", 40) is False
    assert kleinanzeigen_provider._matches_location(potsdam_job, "Berlin", "3331", 40) is True
    assert kleinanzeigen_provider._matches_location(hamburg_job, "Berlin", "3331", 40) is False


def test_kleinanzeigen_listing_age_supports_relative_and_german_dates():
    assert kleinanzeigen_provider._listing_date("Heute, 09:00", date(2026, 8, 23)) == date(2026, 8, 23)
    assert kleinanzeigen_provider._listing_date("Gestern, 10:35", date(2026, 8, 23)) == date(2026, 8, 22)
    assert kleinanzeigen_provider._listing_date("vor 2 Wochen", date(2026, 8, 23)) == date(2026, 8, 9)
    assert kleinanzeigen_provider._listing_date("22.08.2026", date(2026, 8, 23)) == date(2026, 8, 22)


def test_kleinanzeigen_listing_age_keeps_unknown_dates_but_rejects_known_old_dates():
    job = parse_kleinanzeigen_search_html(SEARCH_HTML)[0]
    assert kleinanzeigen_provider._within_max_age(job, 7, date(2026, 8, 23)) is True
    job.created_at = "01.01.2026"
    assert kleinanzeigen_provider._within_max_age(job, 30, date(2026, 8, 23)) is False
    job.created_at = "Auf Anfrage"
    assert kleinanzeigen_provider._within_max_age(job, 7, date(2026, 8, 23)) is True


def test_balanced_active_search_interleaves_profile_and_german_work_time_queries():
    terms = prepare_kleinanzeigen_search_terms(["Quality Control", "Production Planning"], "both", 8)
    assert terms[:4] == [
        "Quality Control",
        "Production Planning",
        "Qualitätsprüfer",
        "Arbeitsvorbereitung",
    ]
    assert "Quality Control Vollzeit" in terms
    assert "Production Planning Vollzeit" in terms
    assert len(terms) == 8


def test_focused_active_search_respects_source_arrangement_without_expansion():
    assert prepare_kleinanzeigen_search_terms(["Quality Control"], "part_time", 8, "focused") == [
        "Quality Control Teilzeit"
    ]


def test_detail_enrichment_prioritizes_cards_missing_analysis_evidence():
    complete = parse_kleinanzeigen_search_html(SEARCH_HTML)[0]
    incomplete = parse_kleinanzeigen_search_html(SEARCH_HTML)[0]
    complete.external_id = "complete"
    complete.description = "Vollzeit " + ("detailed quality inspection responsibilities " * 8)
    incomplete.external_id = "incomplete"
    incomplete.description = ""
    incomplete.company = ""
    assert sorted([complete, incomplete], key=kleinanzeigen_provider._detail_priority)[0].external_id == "incomplete"
