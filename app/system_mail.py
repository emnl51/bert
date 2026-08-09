import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.parse import urlsplit

from .config import settings
from .db import get_setting, set_setting


class SystemMailError(RuntimeError):
    pass


_SYSTEM_MAIL_DEFAULTS = {
    "public_base_url": lambda: settings.public_base_url,
    "registration_lifetime_hours": lambda: str(settings.registration_lifetime_hours),
    "system_smtp_host": lambda: settings.system_smtp_host,
    "system_smtp_port": lambda: str(settings.system_smtp_port),
    "system_smtp_username": lambda: settings.system_smtp_username,
    "system_smtp_password": lambda: settings.system_smtp_password,
    "system_smtp_use_tls": lambda: str(settings.system_smtp_use_tls).lower(),
    "system_email_from": lambda: settings.system_email_from,
}


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _email_address(value: str, label: str) -> str:
    address = value.strip()
    parsed = parseaddr(address)[1]
    if parsed != address or "@" not in address or any(char in address for char in "\r\n"):
        raise SystemMailError(f"{label} is not a valid email address")
    return address


def get_system_mail_config(mask_secret: bool = False) -> dict:
    values = {key: get_setting(key, default_factory()) for key, default_factory in _SYSTEM_MAIL_DEFAULTS.items()}
    try:
        port = int(values["system_smtp_port"])
        lifetime = int(values["registration_lifetime_hours"])
    except (TypeError, ValueError) as exc:
        raise SystemMailError("Stored system email settings are invalid") from exc
    password = values["system_smtp_password"]
    result = {
        **values,
        "system_smtp_port": port,
        "registration_lifetime_hours": lifetime,
        "system_smtp_use_tls": _as_bool(values["system_smtp_use_tls"]),
        "configured": bool(
            values["public_base_url"].strip()
            and values["system_smtp_host"].strip()
            and values["system_email_from"].strip()
        ),
    }
    if mask_secret:
        result["system_smtp_password"] = "configured" if password else ""
    return result


def save_system_mail_config(data: dict) -> None:
    for key in (
        "public_base_url",
        "registration_lifetime_hours",
        "system_smtp_host",
        "system_smtp_port",
        "system_smtp_username",
        "system_smtp_use_tls",
        "system_email_from",
    ):
        value = data[key]
        set_setting(key, str(value).lower() if isinstance(value, bool) else str(value))
    if data.get("system_smtp_password"):
        set_setting("system_smtp_password", data["system_smtp_password"], is_secret=True)


def registration_lifetime_hours() -> int:
    return max(1, min(168, int(get_system_mail_config()["registration_lifetime_hours"])))


def activation_url(token: str) -> str:
    base = get_system_mail_config()["public_base_url"].strip().rstrip("/")
    if not base:
        raise SystemMailError("PUBLIC_BASE_URL is not configured")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SystemMailError("PUBLIC_BASE_URL must be an absolute HTTP or HTTPS URL")
    return f"{base}/activate?token={token}"


def _send(message: EmailMessage, cfg: dict) -> None:
    if not cfg["system_smtp_host"] or not cfg["system_email_from"]:
        raise SystemMailError("System email is not configured")
    try:
        with smtplib.SMTP(cfg["system_smtp_host"], cfg["system_smtp_port"], timeout=30) as smtp:
            if cfg["system_smtp_use_tls"]:
                smtp.starttls()
            if cfg["system_smtp_username"]:
                smtp.login(cfg["system_smtp_username"], cfg["system_smtp_password"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise SystemMailError(f"System email could not be sent: {exc}") from exc


def send_activation_email(email: str, token: str) -> None:
    cfg = get_system_mail_config()
    url = activation_url(token)
    message = EmailMessage()
    message["Subject"] = f"Activate your {settings.app_name} account"
    message["From"] = _email_address(cfg["system_email_from"], "From address")
    message["To"] = _email_address(email, "Recipient")
    message.set_content(
        f"We received a request to create a {settings.app_name} account for this email address.\n\n"
        f"Verify your email and create your account using this one-time link:\n{url}\n\n"
        f"The link expires in {registration_lifetime_hours()} hours. "
        "If you did not request an account, you can ignore this email."
    )
    _send(message, cfg)


def send_test_email(email: str) -> None:
    cfg = get_system_mail_config()
    message = EmailMessage()
    message["Subject"] = f"{settings.app_name} system email test"
    message["From"] = _email_address(cfg["system_email_from"], "From address")
    message["To"] = _email_address(email, "Recipient")
    message.set_content(
        f"This is a system email test from {settings.app_name}.\n\n"
        "Account activation messages will use this SMTP configuration."
    )
    _send(message, cfg)
