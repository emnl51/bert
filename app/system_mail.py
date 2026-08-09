import smtplib
from email.message import EmailMessage

from .config import settings


class SystemMailError(RuntimeError):
    pass


def activation_url(token: str) -> str:
    base = settings.public_base_url.strip().rstrip("/")
    if not base:
        raise SystemMailError("PUBLIC_BASE_URL is not configured")
    return f"{base}/activate?token={token}"


def send_activation_email(email: str, token: str) -> None:
    if not settings.system_smtp_host or not settings.system_email_from:
        raise SystemMailError("System email is not configured")
    url = activation_url(token)
    message = EmailMessage()
    message["Subject"] = f"Activate your {settings.app_name} account"
    message["From"] = settings.system_email_from
    message["To"] = email
    message.set_content(
        f"We received a request to create a {settings.app_name} account for this email address.\n\n"
        f"Verify your email and create your account using this one-time link:\n{url}\n\n"
        f"The link expires in {settings.registration_lifetime_hours} hours. "
        "If you did not request an account, you can ignore this email."
    )
    try:
        with smtplib.SMTP(settings.system_smtp_host, settings.system_smtp_port, timeout=30) as smtp:
            if settings.system_smtp_use_tls:
                smtp.starttls()
            if settings.system_smtp_username:
                smtp.login(settings.system_smtp_username, settings.system_smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise SystemMailError(f"Activation email could not be sent: {exc}") from exc
