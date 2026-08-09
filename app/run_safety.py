from .db import connection, list_sources


def scrub_run_history_secrets() -> int:
    secrets = []
    for source in list_sources(mask_secrets=False):
        for value in (source.get("secrets") or {}).values():
            if value:
                secrets.append(str(value))
    if not secrets:
        return 0

    changed = 0
    with connection() as con:
        rows = con.execute(
            "SELECT id,provider_errors_json,error,notification_channels_json FROM search_runs"
        ).fetchall()
        for row in rows:
            provider_errors = row["provider_errors_json"] or "[]"
            error = row["error"] or ""
            channels = row["notification_channels_json"] or "[]"
            new_provider, new_error, new_channels = provider_errors, error, channels
            for secret in secrets:
                new_provider = new_provider.replace(secret, "***")
                new_error = new_error.replace(secret, "***")
                new_channels = new_channels.replace(secret, "***")
            if (new_provider, new_error, new_channels) != (provider_errors, error, channels):
                con.execute(
                    "UPDATE search_runs SET provider_errors_json=?,error=?,notification_channels_json=? WHERE id=?",
                    (new_provider, new_error, new_channels, row["id"]),
                )
                changed += 1
    return changed
