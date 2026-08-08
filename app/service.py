from .db import create_run, finish_run, mark_notified, upsert_job
from .notifier import send_email, send_telegram
from .providers import fetch_all_jobs
from .ranker import assess_language_fit, calculate_overall_score, score_job
from .runtime import runtime_config


async def run_search() -> dict:
    run_id = create_run()
    cfg = runtime_config()
    provider_errors: list[str] = []
    notification_channels: list[str] = []
    try:
        search_terms = list(cfg['keywords'].get('search', {}).keys())
        fetched, provider_errors = await fetch_all_jobs(cfg['sources'], search_terms, cfg['target_location'])
        fresh_matches = []
        language_profile = {
            'primary_working_language': cfg['primary_working_language'],
            'current_german_level': cfg['current_german_level'],
            'max_german_requirement': cfg['max_german_requirement'],
            'prefer_german_growth': cfg['prefer_german_growth'],
        }
        for job in fetched:
            job.score, job.reasons = score_job(job, cfg['keywords'], cfg['location_terms'])
            job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)
            job.overall_score = calculate_overall_score(job.score, job.language_score, cfg['language_weight'])
            is_new = upsert_job(job)
            eligible_language = job.language_score >= cfg['min_language_score']
            if cfg['hide_german_heavy'] and job.language_label == 'german_heavy':
                eligible_language = False
            if not cfg['show_b2_stretch'] and job.language_label == 'stretch':
                eligible_language = False
            if is_new and job.overall_score >= cfg['min_score'] and eligible_language:
                fresh_matches.append(job)
        fresh_matches.sort(key=lambda j: (j.overall_score, j.language_score, j.score), reverse=True)
        fresh_matches = fresh_matches[:cfg['max_digest_jobs']]

        if fresh_matches:
            try:
                if send_email(fresh_matches, cfg):
                    notification_channels.append('email')
            except Exception as exc:
                notification_channels.append(f'email-error:{exc}')
            try:
                if await send_telegram(fresh_matches, cfg):
                    notification_channels.append('telegram')
            except Exception as exc:
                notification_channels.append(f'telegram-error:{exc}')
            if any(x in ('email', 'telegram') for x in notification_channels):
                mark_notified([j.key for j in fresh_matches])

        result = {
            'run_id': run_id, 'fetched': len(fetched), 'new_matches': len(fresh_matches),
            'provider_errors': provider_errors, 'notification_channels': notification_channels,
            'matches': [
                {
                    'title': j.title, 'company': j.company, 'location': j.location,
                    'job_fit': j.score, 'language_fit': j.language_score, 'overall': j.overall_score,
                    'language_label': j.language_label, 'url': j.url,
                    'reasons': j.reasons, 'language_reasons': j.language_reasons,
                }
                for j in fresh_matches
            ],
        }
        finish_run(run_id, status='success', fetched=len(fetched), new_matches=len(fresh_matches), provider_errors=provider_errors, notification_channels=notification_channels)
        return result
    except Exception as exc:
        finish_run(run_id, status='error', provider_errors=provider_errors, notification_channels=notification_channels, error=str(exc))
        raise
