from .config import settings
from .db import get_setting, list_sources, active_keyword_map


def _int(key: str, default: int) -> int:
    try:
        return int(get_setting(key, str(default)))
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    value = get_setting(key, str(default).lower()).lower()
    return value in ('1', 'true', 'yes', 'on')


def runtime_config() -> dict:
    return {
        'target_location': get_setting('target_location', settings.target_location),
        'location_terms': [x.strip().lower() for x in get_setting('location_terms', 'berlin').split(',') if x.strip()],
        'min_score': _int('min_score', settings.min_score),
        'max_digest_jobs': _int('max_digest_jobs', settings.max_digest_jobs),
        'timezone': get_setting('timezone', settings.timezone),
        'schedule_frequency': get_setting('schedule_frequency', settings.schedule_frequency),
        'schedule_day': get_setting('schedule_day', settings.schedule_day),
        'schedule_hour': _int('schedule_hour', settings.schedule_hour),
        'schedule_minute': _int('schedule_minute', settings.schedule_minute),
        'schedule_interval_hours': _int('schedule_interval_hours', settings.schedule_interval_hours),
        'smtp_host': get_setting('smtp_host', settings.smtp_host),
        'smtp_port': _int('smtp_port', settings.smtp_port),
        'smtp_username': get_setting('smtp_username', settings.smtp_username),
        'smtp_password': get_setting('smtp_password', settings.smtp_password),
        'smtp_use_tls': _bool('smtp_use_tls', settings.smtp_use_tls),
        'email_from': get_setting('email_from', settings.email_from),
        'email_to': get_setting('email_to', settings.email_to),
        'telegram_bot_token': get_setting('telegram_bot_token', settings.telegram_bot_token),
        'telegram_chat_id': get_setting('telegram_chat_id', settings.telegram_chat_id),
        'sources': [s for s in list_sources(mask_secrets=False) if s['enabled']],
        'keywords': active_keyword_map(),
    }
