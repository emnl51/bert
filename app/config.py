from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JobTrack"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    database_path: str = "/data/jobs.db"
    app_secret_key: str = "change-this-secret-key"
    admin_username: str = "admin"
    admin_password: str = "change-me"

    # Optional host-side updater. The updater owns Docker/Git privileges; the
    # web container can only reach its narrow API through a Unix socket.
    update_agent_socket: str = ""
    update_agent_token: str = ""
    update_agent_timeout_seconds: float = 5.0

    timezone: str = "Europe/Berlin"
    schedule_frequency: str = "weekly"
    schedule_day: str = "mon"
    schedule_hour: int = 8
    schedule_minute: int = 0
    schedule_interval_hours: int = 12
    run_on_start: bool = False

    target_location: str = "Berlin"
    adzuna_distance_km: int = 40
    arbeitnow_pages: int = 5
    results_per_term: int = 50
    min_score: int = 35
    max_digest_jobs: int = 20

    # Migration/fallback values: UI-managed secrets take precedence after first save.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = ""
    email_to: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()


INSECURE_VALUES = {
    "ADMIN_PASSWORD": {"", "change-me", "replace-with-a-long-unique-password"},
    "APP_SECRET_KEY": {
        "",
        "change-this-secret-key",
        "replace-with-at-least-32-random-characters",
    },
}


def validate_secure_settings() -> None:
    """Refuse to serve with the published placeholder credentials."""
    insecure = [name for name, values in INSECURE_VALUES.items() if getattr(settings, name.lower()) in values]
    if insecure:
        names = ", ".join(insecure)
        raise RuntimeError(
            f"Insecure default configuration for {names}. "
            "Set strong, unique values in the environment before starting JobTrack."
        )
