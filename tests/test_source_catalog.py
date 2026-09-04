from app.source_catalog import SOURCE_CATALOG, render_search_url


def test_catalog_contains_requested_platforms():
    keys = {x["key"] for x in SOURCE_CATALOG}
    expected = {
        "indeed",
        "stepstone",
        "arbeitsagentur",
        "jooble",
        "greenhouse",
        "lever",
        "smartrecruiters",
        "rss",
    }
    assert expected.issubset(keys)


def test_catalog_only_keeps_useful_manual_search_shortcuts():
    manual_keys = {x["key"] for x in SOURCE_CATALOG if x["mode"] == "search-only"}
    assert manual_keys == {"indeed", "stepstone-search", "arbeitsagentur"}


def test_arbeitsagentur_uses_current_jobs_search_parameters():
    source = next(x for x in SOURCE_CATALOG if x["key"] == "arbeitsagentur")
    url = render_search_url(source["url_template"], "quality engineer", "Berlin")
    assert "suchbereich=jobs" in url
    assert "was=quality+engineer" in url
    assert "wo=Berlin" in url


def test_search_url_is_encoded():
    url = render_search_url(
        "https://example.com?q={query}&l={location}",
        "supply chain",
        "Berlin Mitte",
    )
    assert "supply+chain" in url
    assert "Berlin+Mitte" in url


def test_search_only_entries_do_not_claim_api_mode():
    search_only = [x for x in SOURCE_CATALOG if x["mode"] == "search-only"]
    assert search_only
    assert all(x["source_type"] == "search_link" for x in search_only)
