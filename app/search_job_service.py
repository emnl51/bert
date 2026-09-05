import asyncio
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit
from .db import list_sources, mark_notified, upsert_job
from .employment_filter import (
    assess_employment_fit,
    is_hard_employment_exclusion,
    profile_requires_confirmed_work_time,
    search_terms_for_profile,
)
from .job_enrichment import enrich_jobs
from .language_store import upsert_language_fit
from .notifier import send_email, send_telegram
from .positive_learning import apply_positive_boost, sync_application_events
from .feedback_store import apply_learned_penalty
from .profile_store import get_profile, upsert_profile_score
from .providers import fetch_all_jobs
from .ranker import (
    assess_language_fit,
    assess_role_relevance,
    blocklist_matches,
    calculate_overall_score,
    classify_match_tier,
    profile_english_level,
    score_job,
)
from .runtime import runtime_config
from .semantic_ranker import semantic_rerank
from .source_analytics import (
    save_query_run_stats,
    save_search_job_source_stats,
)
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
    """Expand isolated job queries without losing the scoring profile's role coverage."""
    configured = [str(term).strip() for term in (search_job.get("search_terms") or []) if str(term).strip()]
    return search_terms_for_profile(profile, configured if configured else None)


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


_COMPANY_SUFFIX = re.compile(
    r"\b(?:gmbh(?:\s*&\s*co\.?\s*kg)?|ag|se|kg|ug|ltd|limited|inc|corp|corporation|group)\b",
    re.IGNORECASE,
)
_TITLE_NOISE = re.compile(
    r"\b(?:m\s*/\s*w\s*/\s*d|w\s*/\s*m\s*/\s*d|all genders|gn|f\s*/\s*m\s*/\s*d)\b",
    re.IGNORECASE,
)


def _company_signature(value: str) -> str:
    return normalize_text(_COMPANY_SUFFIX.sub(" ", str(value or "")))


def _title_signature(value: str) -> str:
    return normalize_text(_TITLE_NOISE.sub(" ", str(value or "")))


def _tokens(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if len(token) >= 3}


def _jaccard(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _same_vacancy(left, right) -> bool:
    left_url, right_url = _canonical_url(getattr(left, "url", "")), _canonical_url(getattr(right, "url", ""))
    left_title, right_title = (
        _title_signature(getattr(left, "title", "")),
        _title_signature(getattr(right, "title", "")),
    )
    if left_url and right_url and left_url == right_url:
        return left_title == right_title or _jaccard(left_title, right_title) >= 0.5
    companies = (_company_signature(getattr(left, "company", "")), _company_signature(getattr(right, "company", "")))
    if not companies[0] or companies[0] != companies[1]:
        return False
    locations = (normalize_text(getattr(left, "location", "")), normalize_text(getattr(right, "location", "")))
    if locations[0] and locations[1] and _jaccard(*locations) < 0.5:
        return False
    return left_title == right_title or _jaccard(left_title, right_title) >= 0.85


def _source_option(job) -> dict[str, str]:
    return {
        "source": str(getattr(job, "source", "")),
        "url": str(getattr(job, "url", "")),
        "external_id": str(getattr(job, "external_id", "")),
    }


def _merge_vacancy(current, candidate):
    options = [*(getattr(current, "source_options", []) or [_source_option(current)])]
    for option in getattr(candidate, "source_options", []) or [_source_option(candidate)]:
        if option not in options:
            options.append(option)
    queries = list(
        dict.fromkeys(
            [
                *(getattr(current, "discovered_queries", []) or []),
                *(getattr(candidate, "discovered_queries", []) or []),
            ]
        )
    )
    winner = (
        candidate
        if len(getattr(candidate, "description", "") or "") > len(getattr(current, "description", "") or "")
        else current
    )
    winner.source_options = options
    winner.discovered_queries = queries
    return winner


def deduplicate_jobs(jobs: list) -> list:
    """Cluster cross-source duplicates while preserving provenance and evidence."""
    unique: list[object] = []
    company_buckets: dict[str, list[int]] = defaultdict(list)
    for job in jobs:
        job.source_options = getattr(job, "source_options", []) or [_source_option(job)]
        company = _company_signature(getattr(job, "company", ""))
        candidates = company_buckets.get(company, []) if company else range(len(unique))
        matched_index = next((index for index in candidates if _same_vacancy(unique[index], job)), None)
        if matched_index is None:
            matched_index = len(unique)
            unique.append(job)
            if company:
                company_buckets[company].append(matched_index)
        else:
            unique[matched_index] = _merge_vacancy(unique[matched_index], job)
    return unique


def passes_candidate_threshold(analysis: dict | None, minimum: int) -> bool:
    return bool(analysis) and int(analysis.get("cv_match", 0)) >= max(0, min(100, int(minimum)))


def has_sufficient_candidate_evidence(job) -> bool:
    """Return whether a provider supplied enough vacancy text for a hard CV gate."""
    description = normalize_text(getattr(job, "description", ""))
    return len(description) >= 240 and len(description.split()) >= 35


def _job_sources(job) -> list[str]:
    options = getattr(job, "source_options", []) or []
    sources = [str(option.get("source") or "") for option in options if option.get("source")]
    return list(dict.fromkeys(sources or [str(getattr(job, "source", "Unknown"))]))


def _increment(stats: dict, keys, field: str) -> None:
    for key in keys:
        stats[key][field] += 1


def _save_analytics(run_id: int, search_job: dict, source_stats: dict, query_stats: dict) -> None:
    """Keep optional analytics failures from breaking a successful search."""
    try:
        save_search_job_source_stats(
            run_id,
            int(search_job["id"]),
            dict(source_stats),
            user_id=search_job.get("user_id"),
        )
        save_query_run_stats(
            run_id,
            int(search_job["id"]),
            dict(query_stats),
            user_id=search_job.get("user_id"),
        )
    except Exception:
        return


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
    filtered = {"blocklist": 0, "role": 0, "employment": 0, "fit": 0, "language": 0, "cv_match": 0}
    source_stats = defaultdict(
        lambda: {
            "fetched": 0,
            "unique_jobs": 0,
            "role_fit": 0,
            "employment_fit": 0,
            "language_fit": 0,
            "recommended": 0,
            "new_matches": 0,
        }
    )
    query_stats = defaultdict(lambda: {"fetched": 0, "recommended": 0, "new_matches": 0})
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
        for source_job in fetched:
            _increment(source_stats, [source_job.source], "fetched")
            for query in getattr(source_job, "discovered_queries", []) or []:
                query_stats[query]["fetched"] += 1
        unique_jobs = deduplicate_jobs(fetched)
        enrichment = await enrich_jobs(
            unique_jobs,
            limit=12 if profile_requires_confirmed_work_time(profile) else 8,
            priority_terms=search_terms,
        )
        for source_job in unique_jobs:
            _increment(source_stats, _job_sources(source_job), "unique_jobs")
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
        strict_employment = search_job.get("employment_mode", "prefer") == "strict"
        custom_role_intent = bool(search_job.get("search_terms"))
        for source_job in unique_jobs:
            job = deepcopy(source_job)
            if blocklist_matches(job, keyword_rules):
                filtered["blocklist"] += 1
                continue
            job.score, job.reasons = score_job(
                job,
                keyword_rules,
                location_terms,
                search_terms,
                restrict_to_intent=custom_role_intent,
            )
            role = assess_role_relevance(
                job,
                keyword_rules,
                search_terms,
                restrict_to_intent=custom_role_intent,
                role_level=profile.get("role_level", "any"),
            )
            job.role_relevant = role.relevant
            job.reasons.extend(reason for reason in role.reasons if reason not in job.reasons)
            employment_ok, _employment_label, employment_reasons = assess_employment_fit(
                job, profile, strict=strict_employment
            )
            job.reasons.extend(employment_reasons)
            job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)
            job.score, neg = apply_learned_penalty(job, job.score, profile_id=profile["id"])
            job.reasons.extend(neg)
            job.score, pos = apply_positive_boost(job, job.score, profile_id=profile["id"])
            job.reasons.extend(pos)
            job.overall_score = calculate_overall_score(job.score, job.language_score, profile["language_weight"])
            upsert_job(job)
            upsert_language_fit(job)
            if not role.relevant:
                filtered["role"] += 1
                job.match_tier = "excluded"
                upsert_profile_score(job, profile["id"], role_relevant=False, match_tier="excluded")
                continue
            _increment(source_stats, _job_sources(job), "role_fit")

            hard_employment_exclusion = is_hard_employment_exclusion(
                profile,
                employment_ok,
                _employment_label,
                strict=strict_employment,
            )
            if hard_employment_exclusion:
                filtered["employment"] += 1
                job.match_tier = "excluded"
                upsert_profile_score(job, profile["id"], role_relevant=True, match_tier="excluded")
                continue
            if employment_ok:
                _increment(source_stats, _job_sources(job), "employment_fit")
            if job.language_score >= min_lang:
                _increment(source_stats, _job_sources(job), "language_fit")

            eligible = employment_ok and job.language_score >= min_lang and job.overall_score >= min_score
            if not employment_ok:
                filtered["employment"] += 1
            elif job.overall_score < min_score:
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
            cv_deferred = False
            if eligible and candidate:
                if not has_sufficient_candidate_evidence(job):
                    cv_deferred = True
                    job.reasons.append("cv match deferred: source description incomplete")
                else:
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
                        cv_deferred = True
                        job.reasons.append(f"intelligence-error: {exc}")
                        job.reasons.append("cv match deferred: analysis unavailable")
                    if not cv_deferred and not getattr(job, "intelligence", None):
                        cv_deferred = True
                        job.reasons.append("cv match deferred: analysis unavailable")
                    elif not cv_deferred and not passes_candidate_threshold(job.intelligence, min_cv_match):
                        filtered["cv_match"] += 1
                        eligible = False
            job.match_tier = classify_match_tier(
                role_relevant=True,
                eligible=eligible,
                overall_score=job.overall_score,
                employment_constraint=any(reason.startswith("employment mismatch:") for reason in employment_reasons),
                language_label=job.language_label,
                evidence_constraint=cv_deferred,
            )
            upsert_profile_score(job, profile["id"], role_relevant=True, match_tier=job.match_tier)
            if eligible:
                _increment(source_stats, _job_sources(job), "recommended")
                for query in getattr(job, "discovered_queries", []) or []:
                    query_stats[query]["recommended"] += 1
                fresh_for_this_search = mark_search_job_seen(search_job_id, job.key)
                if fresh_for_this_search:
                    _increment(source_stats, _job_sources(job), "new_matches")
                    for query in getattr(job, "discovered_queries", []) or []:
                        query_stats[query]["new_matches"] += 1
                    matches.append(job)
        semantic = await semantic_rerank(matches, profile, user_id=search_job.get("user_id"))
        matches.sort(
            key=lambda j: (
                {"strong": 2, "match": 1, "stretch": 0}.get(getattr(j, "match_tier", "match"), 0),
                getattr(j, "intelligence", {}).get("cv_match", -1),
                getattr(j, "hybrid_rank_score", j.overall_score),
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
        _save_analytics(run_id, search_job, source_stats, query_stats)
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
            "detail_enrichment": enrichment,
            "matches": len(matches),
            "filtered": filtered,
            "provider_errors": provider_errors,
            "notification_channels": channels,
            "semantic_rerank": semantic,
        }
    except Exception as exc:
        _save_analytics(run_id, search_job, source_stats, query_stats)
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
