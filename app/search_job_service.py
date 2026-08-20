import asyncio
import uuid
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit
from .db import list_sources, mark_notified, upsert_job
from .employment_filter import assess_employment_fit, search_terms_for_profile
from .language_store import upsert_language_fit
from .notifier import send_email, send_telegram
from .positive_learning import apply_positive_boost, sync_application_events
from .feedback_store import apply_learned_penalty
from .profile_store import get_profile, upsert_profile_score
from .providers import fetch_all_jobs
from .ranker import assess_language_fit, blocklist_matches, calculate_overall_score, profile_english_level, score_job
from .runtime import runtime_config
from .search_job_store import (
    acquire_search_job_lock,
    create_search_job_run,
    finish_search_job_run,
    get_search_job_any,
    mark_search_job_seen,
    release_search_job_lock,
)
from .candidate_store import candidate_for_search_job
from .intelligence import analyze_job
from .text_match import normalize_text


def _notification_cfg(search_job: dict, base_cfg: dict) -> dict:
    cfg = dict(base_cfg)
    n = search_job.get("notification") or {}
    s = search_job.get("secrets") or {}
    for key in (
        "telegram_chat_id",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_use_tls",
        "email_from",
        "email_to",
    ):
        if n.get(key) not in (None, ""):
            cfg[key] = n[key]
    for key in ("telegram_bot_token", "smtp_password"):
        if s.get(key) not in (None, "", "configured"):
            cfg[key] = s[key]
    return cfg


def _selected_sources(search_job: dict) -> list[dict]:
    enabled = [s for s in list_sources(mask_secrets=False) if s["enabled"]]
    ids = {int(x) for x in (search_job.get("source_ids") or [])}
    return [s for s in enabled if not ids or int(s["id"]) in ids]


def search_terms_for_job(search_job: dict, profile: dict) -> list[str]:
    """Prefer isolated per-job queries and fall back to the scoring profile."""
    configured = [str(term).strip() for term in (search_job.get("search_terms") or []) if str(term).strip()]
    return list(dict.fromkeys(configured)) or search_terms_for_profile(profile)


def keyword_rules_for_job(search_job: dict, profile: dict) -> dict[str, dict[str, int]]:
    """Resolve profile keyword rules with explicit per-job allow/block overrides."""
    keywords = deepcopy(profile.get("keywords") or {})
    allowlist = search_job.get("allowlist_terms")
    blocklist = search_job.get("blocklist_terms")
    if allowlist is not None:
        boost = max(0, int(search_job.get("allowlist_boost", 15)))
        keywords["allowlist"] = {str(term): boost for term in allowlist}
    if blocklist is not None:
        keywords["blocklist"] = {str(term): -100 for term in blocklist}
    return keywords


def _canonical_url(value: str) -> str:
    try:
        parts = urlsplit(str(value or "").strip())
    except ValueError:
        return ""
    host = (parts.hostname or "").removeprefix("www.").lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, "", "")) if host else ""


def _vacancy_identity(job) -> tuple[str, ...]:
    title = normalize_text(getattr(job, "title", ""))
    company = normalize_text(getattr(job, "company", ""))
    location = normalize_text(getattr(job, "location", ""))
    if title and company:
        return ("vacancy", title, company, location)
    canonical_url = _canonical_url(getattr(job, "url", ""))
    if canonical_url:
        return ("url", canonical_url)
    return ("source", str(getattr(job, "key", "")))


def deduplicate_jobs(jobs: list) -> list:
    """Collapse the same vacancy returned by multiple queries or providers.

    The richer description wins so downstream matching keeps the best evidence.
    Stable insertion order makes notification ordering deterministic.
    """
    unique: dict[tuple[str, ...], object] = {}
    for job in jobs:
        identity = _vacancy_identity(job)
        current = unique.get(identity)
        if current is None or len(getattr(job, "description", "") or "") > len(
            getattr(current, "description", "") or ""
        ):
            unique[identity] = job
    return list(unique.values())


def passes_candidate_threshold(analysis: dict | None, minimum: int) -> bool:
    return bool(analysis) and int(analysis.get("cv_match", 0)) >= max(0, min(100, int(minimum)))


async def run_search_job(search_job_id: int) -> dict:
    search_job = get_search_job_any(search_job_id, mask_secrets=False)
    if not search_job:
        raise ValueError("Search job not found")
    lock_owner = uuid.uuid4().hex
    if not acquire_search_job_lock(search_job_id, lock_owner):
        raise RuntimeError("Search job is already running in another worker")
    run_id = create_search_job_run(search_job_id)
    base_cfg = runtime_config(search_job.get("user_id"))
    provider_errors = []
    channels = []
    filtered = {"blocklist": 0, "employment": 0, "fit": 0, "language": 0, "cv_match": 0}
    try:
        profile = get_profile(int(search_job["profile_id"]), user_id=search_job.get("user_id"))
        if not profile:
            raise ValueError("Search profile not found")
        sync_application_events([profile["id"]], user_id=search_job.get("user_id"))
        candidate = candidate_for_search_job(search_job_id, user_id=search_job.get("user_id"))
        search_terms = search_terms_for_job(search_job, profile)
        if not search_terms:
            raise ValueError("Search job has no search keywords and its profile provides no fallback keywords")
        sources = _selected_sources(search_job)
        target_location = (
            profile.get("target_location", "Berlin")
            if search_job.get("inherit_location")
            else search_job["target_location"]
        )
        fetched, provider_errors = await fetch_all_jobs(sources, search_terms, target_location)
        unique_jobs = deduplicate_jobs(fetched)
        matches = []
        language_profile = {
            "primary_working_language": "English",
            "current_english_level": profile_english_level(profile),
            "current_german_level": profile["current_german_level"],
            "max_german_requirement": profile["max_german_requirement"],
            "prefer_german_growth": profile["prefer_german_growth"],
        }
        min_score = (
            profile["min_score"]
            if search_job.get("min_score_override") is None
            else int(search_job["min_score_override"])
        )
        min_lang = (
            profile["min_language_score"]
            if search_job.get("min_language_score_override") is None
            else int(search_job["min_language_score_override"])
        )
        location_terms = (
            profile.get("location_terms") or []
            if search_job.get("inherit_location")
            else search_job.get("location_terms") or profile.get("location_terms") or []
        )
        keyword_rules = keyword_rules_for_job(search_job, profile)
        min_cv_match = int(search_job.get("min_cv_match", 58))
        for source_job in unique_jobs:
            job = deepcopy(source_job)
            if blocklist_matches(job, keyword_rules):
                filtered["blocklist"] += 1
                continue
            job.score, job.reasons = score_job(job, keyword_rules, location_terms)
            employment_ok, _employment_label, employment_reasons = assess_employment_fit(job, profile)
            if not employment_ok:
                filtered["employment"] += 1
                continue
            job.reasons.extend(employment_reasons)
            job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)
            job.score, neg = apply_learned_penalty(job, job.score, profile_id=profile["id"])
            job.reasons.extend(neg)
            job.score, pos = apply_positive_boost(job, job.score, profile_id=profile["id"])
            job.reasons.extend(pos)
            job.overall_score = calculate_overall_score(job.score, job.language_score, profile["language_weight"])
            upsert_job(job)
            upsert_language_fit(job)
            upsert_profile_score(job, profile["id"])
            eligible = job.language_score >= min_lang and job.overall_score >= min_score
            if job.overall_score < min_score:
                filtered["fit"] += 1
            elif job.language_score < min_lang:
                filtered["language"] += 1
            if profile["hide_german_heavy"] and job.language_label == "german_heavy":
                if eligible:
                    filtered["language"] += 1
                eligible = False
            if not profile["show_b2_stretch"] and job.language_label == "stretch":
                if eligible:
                    filtered["language"] += 1
                eligible = False
            if eligible and candidate:
                try:
                    # Ollama enrichment is synchronous; keep it off the scheduler/event loop.
                    # The worker boundary remains `await asyncio.to_thread(analyze_job`.
                    job.intelligence = await asyncio.to_thread(
                        analyze_job,
                        job.key,
                        candidate["id"],
                        search_job_id,
                        False,
                        search_job.get("user_id"),
                    )
                except Exception as exc:
                    job.reasons.append(f"intelligence-error: {exc}")
                if not passes_candidate_threshold(getattr(job, "intelligence", None), min_cv_match):
                    filtered["cv_match"] += 1
                    eligible = False
            if eligible:
                fresh_for_this_search = mark_search_job_seen(search_job_id, job.key)
                if fresh_for_this_search:
                    matches.append(job)
        matches.sort(
            key=lambda j: (
                getattr(j, "intelligence", {}).get("cv_match", -1),
                j.overall_score,
                j.language_score,
                j.score,
                getattr(j, "created_at", ""),
                j.key,
            ),
            reverse=True,
        )
        matches = matches[: int(search_job.get("max_results") or 20)]
        notify_cfg = _notification_cfg(search_job, base_cfg)
        if matches and search_job.get("notify_email"):
            try:
                if send_email(matches, notify_cfg, title=f"JobTrack · {search_job['name']}"):
                    channels.append("email")
            except Exception as exc:
                channels.append(f"email-error:{exc}")
        if matches and search_job.get("notify_telegram"):
            try:
                if await send_telegram(matches, notify_cfg, title=f"JobTrack · {search_job['name']}"):
                    channels.append("telegram")
            except Exception as exc:
                channels.append(f"telegram-error:{exc}")
        if any(x in ("email", "telegram") for x in channels):
            mark_notified([j.key for j in matches])
        finish_search_job_run(
            run_id,
            search_job_id,
            "success",
            len(fetched),
            len(matches),
            provider_errors,
            channels,
            filter_counts=filtered,
        )
        return {
            "search_job_id": search_job_id,
            "name": search_job["name"],
            "profile": profile["name"],
            "search_terms": search_terms,
            "candidate": candidate["name"] if candidate else None,
            "fetched": len(fetched),
            "unique_fetched": len(unique_jobs),
            "matches": len(matches),
            "filtered": filtered,
            "provider_errors": provider_errors,
            "notification_channels": channels,
        }
    except Exception as exc:
        finish_search_job_run(
            run_id,
            search_job_id,
            "error",
            provider_errors=provider_errors,
            channels=channels,
            filter_counts=filtered,
            error=str(exc),
        )
        raise
    finally:
        release_search_job_lock(search_job_id, lock_owner)
