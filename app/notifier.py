import smtplib
from email.message import EmailMessage
import httpx
from .models import Job


LABELS = {
    "english_first": "English-first",
    "german_growth": "German-growth",
    "stretch": "B2 stretch",
    "german_heavy": "German-heavy",
    "unclear": "Language unclear",
}


def build_text_digest(jobs: list[Job], title: str = "JobTrack") -> str:
    lines = [f"{title} — {len(jobs)} new matches", ""]
    for i, job in enumerate(jobs, 1):
        why = ", ".join(job.reasons[:4])
        language_why = ", ".join(job.language_reasons[:3])
        lines.extend(
            [
                f"{i}. {job.title}",
                f"   {job.company} | {job.location}",
                f"   Overall {job.overall_score}/100 | Job {job.score}/100 | Language {job.language_score}/100",
                f"   Language: {LABELS.get(job.language_label, job.language_label)}",
            ]
        )
        intel = getattr(job, "intelligence", None)
        if intel:
            lines.extend(
                [
                    f"   CV Match: {intel.get('cv_match', 0)}/100 | Recommendation: {str(intel.get('recommendation', 'maybe')).upper()}",
                    f"   CV: {intel.get('summary', '')}",
                ]
            )
        lines.extend(
            [
                f"   Why: {why}",
                f"   Language fit: {language_why}",
                f"   {job.url}",
                "",
            ]
        )
    return "\n".join(lines)


def send_email(jobs: list[Job], cfg: dict, title: str = "JobTrack") -> bool:
    if not (cfg.get("smtp_host") and cfg.get("email_from") and cfg.get("email_to")):
        return False
    msg = EmailMessage()
    msg["Subject"] = f"{title} — {len(jobs)} new matches"
    msg["From"] = cfg["email_from"]
    msg["To"] = cfg["email_to"]
    msg.set_content(build_text_digest(jobs, title=title))
    with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587)), timeout=30) as smtp:
        if cfg.get("smtp_use_tls", True):
            smtp.starttls()
        if cfg.get("smtp_username"):
            smtp.login(cfg["smtp_username"], cfg.get("smtp_password", ""))
        smtp.send_message(msg)
    return True


async def send_telegram(jobs: list[Job], cfg: dict, title: str = "JobTrack") -> bool:
    token, chat_id = cfg.get("telegram_bot_token"), cfg.get("telegram_chat_id")
    if not token or not chat_id:
        return False
    text = build_text_digest(jobs, title=title)
    chunks = [text[i : i + 3800] for i in range(0, len(text), 3800)]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as client:
        for chunk in chunks:
            response = await client.post(
                url, json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
            )
            response.raise_for_status()
    return True


async def test_telegram(cfg: dict) -> bool:
    token, chat_id = cfg.get("telegram_bot_token"), cfg.get("telegram_chat_id")
    if not token or not chat_id:
        raise RuntimeError("Telegram token or chat ID is missing")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "JobTrack: Telegram connection test successful.",
            },
        )
        response.raise_for_status()
    return True


def test_email(cfg: dict) -> bool:
    sample = Job(
        source="test",
        external_id="test",
        title="Connection Test",
        company="JobTrack",
        location="Berlin",
        url="https://example.com",
        score=100,
        language_score=100,
        overall_score=100,
        language_label="english_first",
        reasons=["SMTP connection test"],
        language_reasons=["English working environment"],
    )
    return send_email([sample], cfg)
