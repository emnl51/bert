import asyncio

import httpx

from app.kleinanzeigen_provider import (
    build_kleinanzeigen_search_url,
    fetch_kleinanzeigen,
    parse_kleinanzeigen_detail_html,
    parse_kleinanzeigen_search_html,
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
