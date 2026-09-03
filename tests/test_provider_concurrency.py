import asyncio

from app.models import Job
from app import providers


def test_sources_run_concurrently_but_results_keep_configuration_order(monkeypatch):
    slow_started = asyncio.Event()
    fast_started = asyncio.Event()

    def result(source):
        return Job(
            source=source["name"],
            external_id=source["name"],
            title="Process Engineer",
            company="Example",
            location="Berlin",
            url=f"https://example.com/{source['name']}",
        )

    async def slow(source, _terms, _location):
        slow_started.set()
        await asyncio.wait_for(fast_started.wait(), timeout=1)
        return [result(source)]

    async def fast(source, _terms, _location):
        fast_started.set()
        return [result(source)]

    monkeypatch.setitem(providers.PROVIDERS, "test_slow", slow)
    monkeypatch.setitem(providers.PROVIDERS, "test_fast", fast)
    sources = [
        {"id": 901, "name": "Slow source", "source_type": "test_slow", "config": {}},
        {"id": 902, "name": "Fast source", "source_type": "test_fast", "config": {}},
    ]

    jobs, errors = asyncio.run(providers.fetch_all_jobs(sources, ["process engineer"], "Berlin"))

    assert not errors
    assert slow_started.is_set() and fast_started.is_set()
    assert [job.source for job in jobs] == ["Slow source", "Fast source"]
