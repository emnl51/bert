"""Optional multilingual semantic reranking through a local Ollama endpoint."""

from __future__ import annotations

import math

import httpx

from .db import get_setting


def _enabled(value: str) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _intent_text(profile: dict) -> str:
    keywords = profile.get("keywords") or {}
    terms = []
    for kind in ("title", "search", "skill", "allowlist"):
        terms.extend((keywords.get(kind) or {}).keys())
    return "Target role and requirements: " + "; ".join(dict.fromkeys(str(term) for term in terms))[:6000]


def _job_text(job) -> str:
    return (
        f"Job title: {getattr(job, 'title', '')}. Company: {getattr(job, 'company', '')}. "
        f"Description: {getattr(job, 'description', '')[:6000]}"
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0


async def semantic_rerank(jobs: list, profile: dict, user_id=None) -> dict:
    """Annotate eligible jobs; semantic similarity never changes eligibility."""
    if not jobs:
        return {"enabled": False, "scored": 0}
    try:
        enabled = _enabled(get_setting("semantic_rerank_enabled", "false", user_id=user_id))
    except Exception:
        enabled = False
    if not enabled:
        return {"enabled": False, "scored": 0}
    weight = max(0, min(20, int(get_setting("semantic_weight", "15", user_id=user_id) or 15)))
    if not weight:
        return {"enabled": False, "scored": 0}
    url = get_setting("intelligence_ollama_url", "http://host.docker.internal:11434", user_id=user_id).rstrip("/")
    model = get_setting("semantic_model", "nomic-embed-text", user_id=user_id).strip() or "nomic-embed-text"
    timeout = max(
        10,
        min(int(get_setting("intelligence_ollama_timeout_seconds", "60", user_id=user_id) or 60), 120),
    )
    candidates = jobs[:60]
    inputs = [_intent_text(profile), *[_job_text(job) for job in candidates]]
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url + "/api/embed", json={"model": model, "input": inputs})
            response.raise_for_status()
            embeddings = response.json().get("embeddings") or []
        if len(embeddings) != len(inputs):
            raise ValueError("embedding response size mismatch")
        profile_vector = embeddings[0]
        for job, vector in zip(candidates, embeddings[1:], strict=True):
            job.semantic_score = max(0, min(100, round(_cosine(profile_vector, vector) * 100)))
            job.hybrid_rank_score = round(
                (int(job.overall_score) * (100 - weight) + job.semantic_score * weight) / 100,
                2,
            )
            job.reasons.append(f"semantic similarity: {job.semantic_score}/100 (ranking only)")
        return {"enabled": True, "scored": len(candidates), "model": model, "weight": weight}
    except Exception as exc:
        return {"enabled": True, "scored": 0, "fallback": "deterministic", "error": type(exc).__name__}
