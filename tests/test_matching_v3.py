import asyncio
import json

from app import db
from app.employment_filter import search_terms_for_profile
from app.job_enrichment import enrich_jobs, extract_job_facts, fetch_public_job
from app.models import Job
from app.search_job_service import deduplicate_jobs
from app import semantic_ranker
from app.semantic_ranker import semantic_rerank


def vacancy(source, external_id, title, company="Example GmbH", location="Berlin", description="", url=None):
    return Job(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        url=url or f"https://jobs.example.org/{external_id}",
        description=description,
    )


def test_structured_facts_extract_hours_student_language_experience_and_quality_level():
    facts = extract_job_facts(
        "Werkstudent Qualitätsprüfer (m/w/d)",
        "Du bist immatrikuliert und arbeitest 16-20 Stunden pro Woche. Deutsch A2, English C1. "
        "Idealerweise 2 Jahre Berufserfahrung.",
        "Berlin",
    )

    assert facts["employment_type"] == "part_time"
    assert facts["weekly_hours"] == 20
    assert facts["student_required"] is True
    assert facts["experience_years"] == 2
    assert facts["language_levels"] == {"de": "a2", "en": "c1"}
    assert facts["role_specialization"] == "quality_technician"
    assert facts["evidence"]["weekly_hours"] == ["16-20 Stunden pro Woche"]


def test_public_detail_fetch_rejects_private_addresses_without_request():
    try:
        asyncio.run(fetch_public_job("http://127.0.0.1/admin"))
    except ValueError as exc:
        assert "Private or local" in str(exc)
    else:
        raise AssertionError("private URL must be rejected")


def test_cross_source_dedup_preserves_sources_queries_and_richer_description():
    short = vacancy("Adzuna", "1", "Quality Inspector (m/w/d)", description="Short")
    short.discovered_queries = ["quality inspector"]
    rich = vacancy(
        "StepStone Germany",
        "2",
        "Quality Inspector",
        company="Example AG",
        description="Detailed manufacturing quality inspection role with measurement and incoming goods checks.",
    )
    rich.discovered_queries = ["qualitätsprüfer"]

    result = deduplicate_jobs([short, rich])

    assert len(result) == 1
    assert result[0].source == "StepStone Germany"
    assert {option["source"] for option in result[0].source_options} == {"Adzuna", "StepStone Germany"}
    assert result[0].discovered_queries == ["quality inspector", "qualitätsprüfer"]


def test_job_upsert_keeps_historical_sources_queries_and_richest_description(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    rich = vacancy("Board", "1", "Quality Inspector", description="A detailed quality inspection description.")
    rich.source_options = [{"source": "Board A", "url": "https://a.example/1", "external_id": "1"}]
    rich.discovered_queries = ["quality inspector"]
    db.upsert_job(rich)
    sparse = vacancy("Board", "1", "Quality Inspector", description="Short")
    sparse.source_options = [{"source": "Board B", "url": "https://b.example/2", "external_id": "2"}]
    sparse.discovered_queries = ["qualitätsprüfer"]
    db.upsert_job(sparse)
    with db.connection() as con:
        row = con.execute(
            "SELECT description,source_options_json,discovered_queries_json FROM jobs WHERE job_key=?",
            (rich.key,),
        ).fetchone()
    assert row["description"] == rich.description
    assert {item["source"] for item in json.loads(row["source_options_json"])} == {"Board A", "Board B"}
    assert json.loads(row["discovered_queries_json"]) == ["quality inspector", "qualitätsprüfer"]


def test_dedup_does_not_merge_different_levels_or_locations():
    engineer = vacancy("A", "1", "Quality Engineer", location="Berlin")
    manager = vacancy("B", "2", "Quality Manager", location="Berlin")
    hamburg = vacancy("C", "3", "Quality Engineer", location="Hamburg")
    assert len(deduplicate_jobs([engineer, manager, hamburg])) == 3


def test_semantic_reranker_is_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "jobs.db"))
    db.init_db()
    job = vacancy("A", "1", "Quality Engineer")
    job.overall_score = 70
    result = asyncio.run(semantic_rerank([job], {"keywords": {}}, user_id=None))
    assert result == {"enabled": False, "scored": 0}
    assert job.semantic_score is None


def test_sparse_job_detail_is_enriched_before_matching(monkeypatch):
    irrelevant = vacancy("Board", "0", "Software Developer", description="Short", url="https://jobs.public.test/0")
    job = vacancy("Board", "1", "Qualitätsprüfer", description="Short", url="https://jobs.public.test/1")
    fetched = []

    async def detail(url):
        fetched.append(url)
        return {
            "description": "Vollzeit Qualitätskontrolle mit 40 Stunden pro Woche in der Produktion.",
            "employment_type": "FULL_TIME",
        }

    monkeypatch.setattr("app.job_enrichment.fetch_public_job", detail)
    result = asyncio.run(enrich_jobs([irrelevant, job], limit=1, priority_terms=["qualitätsprüfer"]))
    assert result == {"attempted": 1, "enriched": 1, "failed": 0}
    assert fetched == [job.url]
    assert "40 Stunden" in job.description


def test_semantic_reranker_only_annotates_already_eligible_jobs(monkeypatch):
    values = {
        "semantic_rerank_enabled": "true",
        "semantic_weight": "15",
        "intelligence_ollama_url": "http://ollama:11434",
        "semantic_model": "nomic-embed-text",
        "intelligence_ollama_timeout_seconds": "60",
    }
    monkeypatch.setattr(semantic_ranker, "get_setting", lambda key, default, **_kwargs: values.get(key, default))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[1.0, 0.0], [0.9, 0.1]]}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(semantic_ranker.httpx, "AsyncClient", lambda **_kwargs: Client())
    job = vacancy("Board", "1", "Quality Inspector")
    job.overall_score = 70
    result = asyncio.run(semantic_rerank([job], {"keywords": {"title": {"quality inspector": 30}}}))
    assert result["scored"] == 1
    assert job.semantic_score > 90
    assert job.hybrid_rank_score > job.overall_score


def test_quality_technician_queries_are_prioritized_ahead_of_engineer_aliases():
    profile = {
        "name": "Quality technician",
        "slug": "quality-technician",
        "role_level": "technician",
        "target_location": "Berlin",
        "location_terms": ["berlin"],
        "keywords": {
            "search": {"quality engineer": 0, "qualitätsprüfer": 0},
            "title": {"quality engineer": 30, "qualitätsprüfer": 30},
            "format": {"vollzeit": 10},
        },
    }
    terms = search_terms_for_profile(profile)
    assert terms[:2] == ["quality inspector", "qualitätsprüfer"]
    assert terms.index("quality engineer") > terms.index("qualitätsprüfer")
