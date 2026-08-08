from collections import defaultdict
from copy import deepcopy

from .db import create_run, finish_run, mark_notified, upsert_job
from .employment_filter import assess_employment_fit, search_terms_for_profile
from .feedback_store import apply_learned_penalty
from .positive_learning import apply_positive_boost, sync_application_events
from .notifier import send_email, send_telegram
from .language_store import upsert_language_fit
from .profile_store import ensure_profile_schema, list_profiles, upsert_profile_score
from .providers import fetch_all_jobs
from .ranker import assess_language_fit, calculate_overall_score, score_job
from .runtime import runtime_config
from .source_analytics import ensure_source_analytics_schema, save_source_run_stats


async def run_search() -> dict:
    run_id = create_run()
    cfg = runtime_config()
    provider_errors: list[str] = []
    notification_channels: list[str] = []
    source_stats: dict[str, dict[str, int]] = defaultdict(lambda: {
        'fetched': 0, 'unique_jobs': 0, 'job_fit': 0, 'language_fit': 0, 'recommended': 0, 'new_matches': 0,
    })
    source_seen: dict[str, set[str]] = defaultdict(set)
    try:
        ensure_profile_schema()
        ensure_source_analytics_schema()
        profiles = list_profiles(enabled_only=True)
        if not profiles:
            raise RuntimeError('No enabled search profile')
        sync_application_events([p['id'] for p in profiles])

        # The legacy/global run belongs to the default profile only. Mixing search terms
        # from every enabled profile caused Werkstudent runs to send full-time manager
        # queries to providers. Dedicated Search Jobs remain profile-specific.
        default_profile = next((p for p in profiles if p.get('is_default')), profiles[0])
        search_terms = search_terms_for_profile(default_profile) or list(cfg['keywords'].get('search', {}).keys())
        target_location = default_profile.get('target_location') or cfg['target_location']
        fetched, provider_errors = await fetch_all_jobs(cfg['sources'], search_terms, target_location)

        for raw_job in fetched:
            source_stats[raw_job.source]['fetched'] += 1
            if raw_job.key not in source_seen[raw_job.source]:
                source_seen[raw_job.source].add(raw_job.key)
                source_stats[raw_job.source]['unique_jobs'] += 1

        fresh_matches = []
        profile_match_counts = {p['id']: 0 for p in profiles}

        for raw_job in fetched:
            is_new = None
            default_scored = None
            for profile in profiles:
                job = deepcopy(raw_job)
                keywords = profile.get('keywords') or cfg['keywords']
                location_terms = profile.get('location_terms') or cfg['location_terms']
                job.score, job.reasons = score_job(job, keywords, location_terms)
                employment_ok, _employment_label, employment_reasons = assess_employment_fit(job, profile)
                job.reasons.extend(employment_reasons)

                language_profile = {
                    'primary_working_language': 'English',
                    'current_german_level': profile.get('current_german_level', 'a2_b1'),
                    'max_german_requirement': profile.get('max_german_requirement', 'b1'),
                    'prefer_german_growth': profile.get('prefer_german_growth', True),
                }
                job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)

                job.score, negative_reasons = apply_learned_penalty(job, job.score, profile_id=profile['id'])
                if negative_reasons:
                    job.reasons.extend(negative_reasons)
                job.score, positive_reasons = apply_positive_boost(job, job.score, profile_id=profile['id'])
                if positive_reasons:
                    job.reasons.extend(positive_reasons)

                # Employment format is a hard gate. Learned boosts or language score must
                # never rescue an explicit full-time/unknown-format job for a strict
                # Werkstudent/Part-time profile.
                if not employment_ok:
                    job.score = 0
                    job.overall_score = 0
                else:
                    job.overall_score = calculate_overall_score(job.score, job.language_score, profile.get('language_weight', 35))

                if profile['id'] == default_profile['id']:
                    is_new = upsert_job(job)
                    upsert_language_fit(job)
                    default_scored = job
                    if employment_ok and job.score >= int(profile.get('min_score', 35)):
                        source_stats[job.source]['job_fit'] += 1
                    if employment_ok and job.language_score >= int(profile.get('min_language_score', 40)):
                        source_stats[job.source]['language_fit'] += 1
                elif is_new is None:
                    is_new = upsert_job(job)

                upsert_profile_score(job, profile['id'])

                eligible_language = job.language_score >= int(profile.get('min_language_score', 40))
                if profile.get('hide_german_heavy', True) and job.language_label == 'german_heavy':
                    eligible_language = False
                if not profile.get('show_b2_stretch', True) and job.language_label == 'stretch':
                    eligible_language = False
                eligible = employment_ok and job.overall_score >= int(profile.get('min_score', 35)) and eligible_language
                if eligible:
                    profile_match_counts[profile['id']] += 1
                    if profile['id'] == default_profile['id']:
                        source_stats[job.source]['recommended'] += 1
                        if is_new:
                            source_stats[job.source]['new_matches'] += 1
                            fresh_matches.append(job)

            if default_scored is None and is_new is None:
                upsert_job(raw_job)

        fresh_matches.sort(key=lambda j: (j.overall_score, j.language_score, j.score), reverse=True)
        fresh_matches = fresh_matches[:cfg['max_digest_jobs']]

        if fresh_matches:
            try:
                if send_email(fresh_matches, cfg):
                    notification_channels.append('email')
            except Exception as exc:
                notification_channels.append(f'email-error:{type(exc).__name__}')
            try:
                if await send_telegram(fresh_matches, cfg):
                    notification_channels.append('telegram')
            except Exception as exc:
                notification_channels.append(f'telegram-error:{type(exc).__name__}')
            if any(x in ('email', 'telegram') for x in notification_channels):
                mark_notified([j.key for j in fresh_matches])

        save_source_run_stats(run_id, dict(source_stats))
        result = {
            'run_id': run_id,
            'fetched': len(fetched),
            'new_matches': len(fresh_matches),
            'provider_errors': provider_errors,
            'notification_channels': notification_channels,
            'source_funnel': [{'source': source, **values} for source, values in sorted(source_stats.items())],
            'profiles': [{'id': p['id'], 'name': p['name'], 'matches': profile_match_counts[p['id']]} for p in profiles],
            'matches': [
                {
                    'profile': default_profile['name'], 'title': j.title, 'company': j.company,
                    'location': j.location, 'job_fit': j.score, 'language_fit': j.language_score,
                    'overall': j.overall_score, 'language_label': j.language_label, 'url': j.url,
                    'reasons': j.reasons, 'language_reasons': j.language_reasons,
                }
                for j in fresh_matches
            ],
        }
        finish_run(run_id, status='success', fetched=len(fetched), new_matches=len(fresh_matches), provider_errors=provider_errors, notification_channels=notification_channels)
        return result
    except Exception as exc:
        try:
            if source_stats:
                save_source_run_stats(run_id, dict(source_stats))
        except Exception:
            pass
        finish_run(run_id, status='error', provider_errors=provider_errors, notification_channels=notification_channels, error=f'{type(exc).__name__}: {str(exc)[:300]}')
        raise
