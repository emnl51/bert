"""Explain matching decisions and retain user-labelled regression examples."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from .db import connection
from .employment_filter import assess_employment_fit, is_hard_employment_exclusion
from .feedback_store import apply_learned_penalty
from .job_enrichment import extract_job_facts
from .models import Job
from .positive_learning import apply_positive_boost
from .ranker import (
    assess_language_fit,
    assess_role_relevance,
    blocklist_matches,
    calculate_overall_score,
    profile_english_level,
    score_job,
)
from .search_job_service import keyword_rules_for_job, search_terms_for_job


DIAGNOSTIC_SCHEMA = """
CREATE TABLE IF NOT EXISTS matching_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    search_job_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    expected_relevant INTEGER NOT NULL DEFAULT 1,
    note TEXT NOT NULL DEFAULT '',
    last_prediction INTEGER,
    last_stage TEXT NOT NULL DEFAULT '',
    last_diagnosed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, search_job_id, url),
    FOREIGN KEY(search_job_id) REFERENCES search_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES search_profiles(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_matching_benchmarks_job
    ON matching_benchmarks(user_id, search_job_id, updated_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owner_id(user_id) -> int:
    return int(user_id) if user_id is not None else 0


def ensure_matching_diagnostic_schema() -> None:
    with connection() as con:
        con.executescript(DIAGNOSTIC_SCHEMA)
        con.execute("UPDATE matching_benchmarks SET user_id=0 WHERE user_id IS NULL")


def canonical_url(value: str) -> str:
    try:
        parts = urlsplit(str(value or "").strip())
    except ValueError:
        return ""
    host = (parts.hostname or "").removeprefix("www.").lower()
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), "", "")) if host else ""


def _discovery_status(url: str, search_job_id: int) -> dict:
    wanted = canonical_url(url)
    if not wanted:
        return {"stored": False, "seen_by_search_job": False}
    with connection() as con:
        rows = con.execute(
            "SELECT job_key,url,source,source_options_json FROM jobs WHERE url IS NOT NULL AND url!=''"
        ).fetchall()
        matched = None
        for row in rows:
            urls = [row["url"]]
            try:
                urls.extend(option.get("url", "") for option in json.loads(row["source_options_json"] or "[]"))
            except (TypeError, json.JSONDecodeError):
                pass
            if any(canonical_url(url) == wanted for url in urls):
                matched = row
                break
        if not matched:
            return {"stored": False, "seen_by_search_job": False}
        seen = con.execute(
            "SELECT 1 FROM search_job_seen WHERE search_job_id=? AND job_key=?",
            (search_job_id, matched["job_key"]),
        ).fetchone()
        return {
            "stored": True,
            "seen_by_search_job": bool(seen),
            "job_key": matched["job_key"],
            "source": matched["source"],
        }


def diagnose_job(payload: dict, search_job: dict, profile: dict) -> dict:
    job = Job(
        source="Diagnostic",
        external_id=canonical_url(payload.get("url", "")) or "manual",
        title=str(payload.get("title") or "").strip(),
        company=str(payload.get("company") or "").strip(),
        location=str(payload.get("location") or "").strip(),
        url=str(payload.get("url") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        created_at=str(payload.get("published_at") or "").strip(),
        remote=bool(payload.get("remote", False)),
    )
    search_terms = search_terms_for_job(search_job, profile)
    keywords = keyword_rules_for_job(search_job, profile)
    location_terms = (
        profile.get("location_terms") or []
        if search_job.get("inherit_location")
        else search_job.get("location_terms") or profile.get("location_terms") or []
    )
    min_score = (
        profile["min_score"] if search_job.get("min_score_override") is None else int(search_job["min_score_override"])
    )
    min_language = (
        profile["min_language_score"]
        if search_job.get("min_language_score_override") is None
        else int(search_job["min_language_score_override"])
    )
    strict = search_job.get("employment_mode", "prefer") == "strict"
    custom_intent = bool(search_job.get("search_terms"))
    stages: list[dict] = []

    blocked = blocklist_matches(job, keywords)
    stages.append(
        {
            "stage": "blocklist",
            "passed": not blocked,
            "detail": "No hard exclusion matched" if not blocked else f"Matched: {', '.join(blocked)}",
        }
    )
    job.score, job.reasons = score_job(job, keywords, location_terms, search_terms, restrict_to_intent=custom_intent)
    role = assess_role_relevance(
        job,
        keywords,
        search_terms,
        restrict_to_intent=custom_intent,
        role_level=profile.get("role_level", "any"),
    )
    stages.append(
        {
            "stage": "role",
            "passed": role.relevant,
            "detail": "; ".join(role.reasons),
            "confidence": role.confidence,
            "requested_families": list(role.requested_families),
            "matched_families": list(role.matched_families),
        }
    )
    employment_ok, employment_label, employment_reasons = assess_employment_fit(job, profile, strict=strict)
    hard_employment = is_hard_employment_exclusion(profile, employment_ok, employment_label, strict=strict)
    stages.append(
        {
            "stage": "working_time",
            "passed": not hard_employment and (employment_ok or not strict),
            "hard_exclusion": hard_employment,
            "detail": "; ".join(employment_reasons) or employment_label,
        }
    )
    language_profile = {
        "primary_working_language": "English",
        "current_english_level": profile_english_level(profile),
        "current_german_level": profile["current_german_level"],
        "max_german_requirement": profile["max_german_requirement"],
        "prefer_german_growth": profile["prefer_german_growth"],
    }
    job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)
    stages.append(
        {
            "stage": "language",
            "passed": job.language_score >= min_language,
            "score": job.language_score,
            "threshold": min_language,
            "detail": "; ".join(job.language_reasons) or job.language_label,
        }
    )
    score_before_learning = job.score
    job.score, negative = apply_learned_penalty(job, job.score, profile_id=profile["id"])
    job.score, positive = apply_positive_boost(job, job.score, profile_id=profile["id"])
    stages.append(
        {
            "stage": "learning",
            "passed": True,
            "score_delta": job.score - score_before_learning,
            "detail": "; ".join([*negative, *positive]) or "No learned rule changed this score",
        }
    )
    job.overall_score = calculate_overall_score(job.score, job.language_score, profile["language_weight"])
    stages.append(
        {
            "stage": "fit",
            "passed": job.overall_score >= min_score,
            "score": job.overall_score,
            "job_score": job.score,
            "threshold": min_score,
            "detail": "; ".join(job.reasons[:8]) or "No positive fit evidence",
        }
    )
    language_allowed = not (profile.get("hide_german_heavy") and job.language_label == "german_heavy") and not (
        not profile.get("show_b2_stretch") and job.language_label == "stretch"
    )
    eligible = bool(
        not blocked
        and role.relevant
        and not hard_employment
        and employment_ok
        and job.overall_score >= min_score
        and job.language_score >= min_language
        and language_allowed
    )
    first_failure = next((stage["stage"] for stage in stages if not stage["passed"]), "recommended")
    discovery = _discovery_status(job.url, int(search_job["id"]))
    if not discovery["stored"]:
        summary = "The vacancy has not been stored; retrieval/source coverage is the likely first failure."
    elif eligible:
        summary = "The vacancy passes the current profile and search-job rules."
    else:
        summary = f"The vacancy was found but fails first at the {first_failure} stage."
    return {
        "eligible": eligible,
        "first_failure": first_failure,
        "summary": summary,
        "discovery": discovery,
        "query_plan": search_terms,
        "facts": extract_job_facts(job.title, job.description, job.location),
        "scores": {
            "job": job.score,
            "language": job.language_score,
            "overall": job.overall_score,
            "minimum_overall": min_score,
            "minimum_language": min_language,
        },
        "stages": stages,
    }


def save_benchmark(payload: dict, search_job: dict, profile: dict, diagnosis: dict, user_id=None) -> int:
    ensure_matching_diagnostic_schema()
    now = _now()
    values = (
        _owner_id(user_id),
        int(search_job["id"]),
        int(profile["id"]),
        canonical_url(payload.get("url", "")) or str(payload.get("url", "")).strip(),
        str(payload.get("title") or "").strip(),
        str(payload.get("company") or "").strip(),
        str(payload.get("location") or "").strip(),
        str(payload.get("description") or "").strip(),
        int(bool(payload.get("expected_relevant", True))),
        str(payload.get("note") or "").strip(),
        int(bool(diagnosis["eligible"])),
        diagnosis["first_failure"],
        now,
        now,
        now,
    )
    with connection() as con:
        con.execute(
            """INSERT INTO matching_benchmarks(
                   user_id,search_job_id,profile_id,url,title,company,location,description,
                   expected_relevant,note,last_prediction,last_stage,last_diagnosed_at,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id,search_job_id,url) DO UPDATE SET
                   profile_id=excluded.profile_id,title=excluded.title,company=excluded.company,
                   location=excluded.location,description=excluded.description,
                   expected_relevant=excluded.expected_relevant,note=excluded.note,
                   last_prediction=excluded.last_prediction,last_stage=excluded.last_stage,
                   last_diagnosed_at=excluded.last_diagnosed_at,updated_at=excluded.updated_at""",
            values,
        )
        row = con.execute(
            "SELECT id FROM matching_benchmarks WHERE user_id=? AND search_job_id=? AND url=?",
            (_owner_id(user_id), int(search_job["id"]), values[3]),
        ).fetchone()
    return int(row["id"])


def list_benchmarks(search_job_id: int, user_id=None) -> list[dict]:
    ensure_matching_diagnostic_schema()
    with connection() as con:
        rows = con.execute(
            """SELECT id,url,title,company,location,expected_relevant,note,last_prediction,
                      last_stage,last_diagnosed_at,updated_at
               FROM matching_benchmarks WHERE user_id=? AND search_job_id=? ORDER BY updated_at DESC""",
            (_owner_id(user_id), search_job_id),
        ).fetchall()
    return [
        {
            **dict(row),
            "expected_relevant": bool(row["expected_relevant"]),
            "last_prediction": None if row["last_prediction"] is None else bool(row["last_prediction"]),
        }
        for row in rows
    ]


def run_benchmarks(search_job: dict, profile: dict, user_id=None) -> dict:
    ensure_matching_diagnostic_schema()
    with connection() as con:
        rows = con.execute(
            "SELECT * FROM matching_benchmarks WHERE user_id=? AND search_job_id=? ORDER BY id",
            (_owner_id(user_id), int(search_job["id"])),
        ).fetchall()
    true_positive = false_positive = false_negative = true_negative = 0
    failures: list[dict] = []
    now = _now()
    with connection() as con:
        for row in rows:
            payload = dict(row)
            diagnosis = diagnose_job(payload, search_job, profile)
            expected = bool(row["expected_relevant"])
            predicted = bool(diagnosis["eligible"])
            if expected and predicted:
                true_positive += 1
            elif expected:
                false_negative += 1
            elif predicted:
                false_positive += 1
            else:
                true_negative += 1
            if expected != predicted:
                failures.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "expected_relevant": expected,
                        "predicted_relevant": predicted,
                        "first_failure": diagnosis["first_failure"],
                    }
                )
            con.execute(
                """UPDATE matching_benchmarks SET last_prediction=?,last_stage=?,last_diagnosed_at=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (int(predicted), diagnosis["first_failure"], now, now, row["id"], _owner_id(user_id)),
            )
    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    return {
        "total": len(rows),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": round(true_positive / precision_denominator, 3) if precision_denominator else None,
        "recall": round(true_positive / recall_denominator, 3) if recall_denominator else None,
        "failures": failures,
    }
