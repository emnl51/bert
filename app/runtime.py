from .config import settings
from .db import get_setting, list_sources, active_keyword_map


def _int(key: str, default: int, user_id: int | None = None) -> int:
    try:
        return int(get_setting(key, str(default), user_id=user_id))
    except ValueError:
        return default


def _bool(key: str, default: bool, user_id: int | None = None) -> bool:
    value = get_setting(key, str(default).lower(), user_id=user_id).lower()
    return value in ("1", "true", "yes", "on")


def runtime_config(user_id: int | None = None) -> dict:
    return {
        "target_location": get_setting("target_location", settings.target_location, user_id=user_id),
        "location_terms": [
            x.strip().lower() for x in get_setting("location_terms", "berlin", user_id=user_id).split(",") if x.strip()
        ],
        "min_score": _int("min_score", settings.min_score, user_id),
        "max_digest_jobs": _int("max_digest_jobs", settings.max_digest_jobs, user_id),
        "timezone": get_setting("timezone", settings.timezone, user_id=user_id),
        "schedule_frequency": get_setting("schedule_frequency", settings.schedule_frequency, user_id=user_id),
        "schedule_day": get_setting("schedule_day", settings.schedule_day, user_id=user_id),
        "schedule_hour": _int("schedule_hour", settings.schedule_hour, user_id),
        "schedule_minute": _int("schedule_minute", settings.schedule_minute, user_id),
        "schedule_interval_hours": _int("schedule_interval_hours", settings.schedule_interval_hours, user_id),
        "primary_working_language": get_setting("primary_working_language", "English", user_id=user_id),
        "current_german_level": get_setting("current_german_level", "a2_b1", user_id=user_id),
        "max_german_requirement": get_setting("max_german_requirement", "b1", user_id=user_id),
        "min_language_score": _int("min_language_score", 40, user_id),
        "language_weight": _int("language_weight", 35, user_id),
        "show_b2_stretch": _bool("show_b2_stretch", True, user_id),
        "hide_german_heavy": _bool("hide_german_heavy", True, user_id),
        "prefer_german_growth": _bool("prefer_german_growth", True, user_id),
        "smtp_host": get_setting("smtp_host", "" if user_id is not None else settings.smtp_host, user_id=user_id),
        "smtp_port": _int("smtp_port", settings.smtp_port, user_id),
        "smtp_username": get_setting(
            "smtp_username", "" if user_id is not None else settings.smtp_username, user_id=user_id
        ),
        "smtp_password": get_setting(
            "smtp_password", "" if user_id is not None else settings.smtp_password, user_id=user_id
        ),
        "smtp_use_tls": _bool("smtp_use_tls", settings.smtp_use_tls, user_id),
        "email_from": get_setting("email_from", "" if user_id is not None else settings.email_from, user_id=user_id),
        "email_to": get_setting("email_to", "" if user_id is not None else settings.email_to, user_id=user_id),
        "telegram_bot_token": get_setting(
            "telegram_bot_token", "" if user_id is not None else settings.telegram_bot_token, user_id=user_id
        ),
        "telegram_chat_id": get_setting(
            "telegram_chat_id", "" if user_id is not None else settings.telegram_chat_id, user_id=user_id
        ),
        "sources": [s for s in list_sources(mask_secrets=False) if s["enabled"]],
        "keywords": active_keyword_map(),
    }
