import asyncio
from copy import deepcopy
from .db import list_sources, mark_notified, upsert_job
from .employment_filter import assess_employment_fit, search_terms_for_profile
from .language_store import upsert_language_fit
from .notifier import send_email, send_telegram
from .positive_learning import apply_positive_boost, sync_application_events
from .feedback_store import apply_learned_penalty
from .profile_store import get_profile, upsert_profile_score
from .providers import fetch_all_jobs
from .ranker import assess_language_fit, calculate_overall_score, score_job
from .runtime import runtime_config
from .search_job_store import create_search_job_run, finish_search_job_run, get_search_job, mark_search_job_seen
from .candidate_store import candidate_for_search_job
from .intelligence import analyze_job


def _notification_cfg(search_job: dict, base_cfg: dict) -> dict:
    cfg = dict(base_cfg)
    n = search_job.get('notification') or {}
    s = search_job.get('secrets') or {}
    for key in ('telegram_chat_id','smtp_host','smtp_port','smtp_username','smtp_use_tls','email_from','email_to'):
        if n.get(key) not in (None,''): cfg[key] = n[key]
    for key in ('telegram_bot_token','smtp_password'):
        if s.get(key) not in (None,'','configured'): cfg[key] = s[key]
    return cfg


def _selected_sources(search_job: dict) -> list[dict]:
    enabled = [s for s in list_sources(mask_secrets=False) if s['enabled']]
    ids = {int(x) for x in (search_job.get('source_ids') or [])}
    return [s for s in enabled if not ids or int(s['id']) in ids]


async def run_search_job(search_job_id: int) -> dict:
    search_job = get_search_job(search_job_id, mask_secrets=False)
    if not search_job: raise ValueError('Search job not found')
    run_id = create_search_job_run(search_job_id)
    base_cfg = runtime_config(); provider_errors=[]; channels=[]
    try:
        sync_application_events()
        profile = get_profile(int(search_job['profile_id']))
        if not profile: raise ValueError('Search profile not found')
        candidate = candidate_for_search_job(search_job_id)
        search_terms = search_terms_for_profile(profile)
        sources = _selected_sources(search_job)
        fetched, provider_errors = await fetch_all_jobs(sources, search_terms, search_job['target_location'])
        matches=[]
        language_profile={
            'primary_working_language':'English','current_german_level':profile['current_german_level'],
            'max_german_requirement':profile['max_german_requirement'],'prefer_german_growth':profile['prefer_german_growth'],
        }
        min_score = profile['min_score'] if search_job.get('min_score_override') is None else int(search_job['min_score_override'])
        min_lang = profile['min_language_score'] if search_job.get('min_language_score_override') is None else int(search_job['min_language_score_override'])
        location_terms = search_job.get('location_terms') or profile.get('location_terms') or []
        for source_job in fetched:
            job = deepcopy(source_job)
            job.score, job.reasons = score_job(job, profile['keywords'], location_terms)
            employment_ok, _employment_label, employment_reasons = assess_employment_fit(job, profile)
            if not employment_ok:
                continue
            job.reasons.extend(employment_reasons)
            job.language_score, job.language_label, job.language_reasons = assess_language_fit(job, language_profile)
            job.score, neg = apply_learned_penalty(job, job.score, profile_id=profile['id']); job.reasons.extend(neg)
            job.score, pos = apply_positive_boost(job, job.score, profile_id=profile['id']); job.reasons.extend(pos)
            job.overall_score = calculate_overall_score(job.score, job.language_score, profile['language_weight'])
            upsert_job(job); upsert_language_fit(job); upsert_profile_score(job, profile['id'])
            eligible = job.language_score >= min_lang and job.overall_score >= min_score
            if profile['hide_german_heavy'] and job.language_label == 'german_heavy': eligible=False
            if not profile['show_b2_stretch'] and job.language_label == 'stretch': eligible=False
            if eligible and candidate:
                try:
                    # Ollama enrichment is synchronous; keep it off the scheduler/event loop.
                    job.intelligence = await asyncio.to_thread(analyze_job, job.key, candidate['id'], search_job_id)
                except Exception as exc:
                    job.reasons.append(f'intelligence-error: {exc}')
            if eligible:
                fresh_for_this_search = mark_search_job_seen(search_job_id, job.key)
                if fresh_for_this_search:
                    matches.append(job)
        matches.sort(key=lambda j:(getattr(j,'intelligence',{}).get('cv_match',-1),j.overall_score,j.language_score,j.score), reverse=True)
        matches=matches[:int(search_job.get('max_results') or 20)]
        notify_cfg=_notification_cfg(search_job,base_cfg)
        if matches and search_job.get('notify_email'):
            try:
                if send_email(matches,notify_cfg, title=f"JobTrack · {search_job['name']}"): channels.append('email')
            except Exception as exc: channels.append(f'email-error:{exc}')
        if matches and search_job.get('notify_telegram'):
            try:
                if await send_telegram(matches,notify_cfg, title=f"JobTrack · {search_job['name']}"): channels.append('telegram')
            except Exception as exc: channels.append(f'telegram-error:{exc}')
        if any(x in ('email','telegram') for x in channels): mark_notified([j.key for j in matches])
        finish_search_job_run(run_id,search_job_id,'success',len(fetched),len(matches),provider_errors,channels)
        return {'search_job_id':search_job_id,'name':search_job['name'],'profile':profile['name'],'candidate':candidate['name'] if candidate else None,'fetched':len(fetched),'matches':len(matches),'provider_errors':provider_errors,'notification_channels':channels}
    except Exception as exc:
        finish_search_job_run(run_id,search_job_id,'error',provider_errors=provider_errors,channels=channels,error=str(exc))
        raise
