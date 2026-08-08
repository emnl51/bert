import re
from .models import Job


def _normalise(value: str) -> str:
    return re.sub(r'\s+', ' ', (value or '').lower()).strip()


def score_job(job: Job, keywords: dict[str, dict[str, int]], location_terms: list[str]) -> tuple[int, list[str]]:
    title = _normalise(job.title)
    body = _normalise(f'{job.title} {job.description}')
    location = _normalise(job.location)
    score = 0
    reasons: list[str] = []

    for term, weight in keywords.get('title', {}).items():
        if term in title:
            score += weight
            reasons.append(f'title: {term}')
    for term, weight in keywords.get('format', {}).items():
        if term in body:
            score += weight
            reasons.append(f'format: {term}')
    for term, weight in keywords.get('skill', {}).items():
        if term in body:
            score += weight
            if len(reasons) < 8:
                reasons.append(f'skill: {term}')
    for term, penalty in keywords.get('negative', {}).items():
        if term in title:
            score += penalty
            reasons.append(f'penalty: {term}')

    if location_terms and any(area in location for area in location_terms):
        score += 12
        reasons.append('target area')
    if job.remote:
        score += 3
    format_terms = keywords.get('format', {})
    if format_terms and not any(term in body for term in format_terms):
        score -= 8
    return max(score, 0), reasons
