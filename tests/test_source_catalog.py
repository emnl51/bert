from app.source_catalog import SOURCE_CATALOG, render_search_url


def test_catalog_contains_requested_platforms():
    keys = {x["key"] for x in SOURCE_CATALOG}
    expected = {
        "linkedin",
        "indeed",
        "stepstone",
        "google",
        "glassdoor",
        "talent",
        "arbeitsagentur",
        "jooble",
        "greenhouse",
        "lever",
        "smartrecruiters",
        "rss",
    }
    assert expected.issubset(keys)


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
