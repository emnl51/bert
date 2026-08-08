from .db import create_run, finish_run, mark_notified, upsert_job
from .notifier import send_email, send_telegram
from .providers import fetch_all_jobs
from .ranker import score_job
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
        for job in fetched:
            job.score, job.reasons = score_job(job, cfg['keywords'], cfg['location_terms'])
            is_new = upsert_job(job)
            if is_new and job.score >= cfg['min_score']:
                fresh_matches.append(job)
        fresh_matches.sort(key=lambda j: j.score, reverse=True)
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
            'matches': [{'title': j.title, 'company': j.company, 'location': j.location, 'score': j.score, 'url': j.url, 'reasons': j.reasons} for j in fresh_matches],
        }
        finish_run(run_id, status='success', fetched=len(fetched), new_matches=len(fresh_matches), provider_errors=provider_errors, notification_channels=notification_channels)
        return result
    except Exception as exc:
        finish_run(run_id, status='error', provider_errors=provider_errors, notification_channels=notification_channels, error=str(exc))
        raise
