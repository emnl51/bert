import smtplib
from email.message import EmailMessage
import httpx
from .models import Job


def build_text_digest(jobs: list[Job]) -> str:
    lines = [f'JobTrack — {len(jobs)} new matches', '']
    for i, job in enumerate(jobs, 1):
        why = ', '.join(job.reasons[:5])
        lines.extend([
            f'{i}. {job.title}', f'   {job.company} | {job.location} | score {job.score}',
            f'   Why: {why}', f'   {job.url}', '',
        ])
    return '\n'.join(lines)


def send_email(jobs: list[Job], cfg: dict) -> bool:
    if not (cfg.get('smtp_host') and cfg.get('email_from') and cfg.get('email_to')):
        return False
    msg = EmailMessage()
    msg['Subject'] = f'Berlin Supply Chain Jobs — {len(jobs)} new matches'
    msg['From'] = cfg['email_from']
    msg['To'] = cfg['email_to']
    msg.set_content(build_text_digest(jobs))
    with smtplib.SMTP(cfg['smtp_host'], int(cfg.get('smtp_port', 587)), timeout=30) as smtp:
        if cfg.get('smtp_use_tls', True):
            smtp.starttls()
        if cfg.get('smtp_username'):
            smtp.login(cfg['smtp_username'], cfg.get('smtp_password', ''))
        smtp.send_message(msg)
    return True


async def send_telegram(jobs: list[Job], cfg: dict) -> bool:
    token, chat_id = cfg.get('telegram_bot_token'), cfg.get('telegram_chat_id')
    if not token or not chat_id:
        return False
    text = build_text_digest(jobs)
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)]
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    async with httpx.AsyncClient(timeout=30) as client:
        for chunk in chunks:
            response = await client.post(url, json={'chat_id': chat_id, 'text': chunk, 'disable_web_page_preview': True})
            response.raise_for_status()
    return True


async def test_telegram(cfg: dict) -> bool:
    token, chat_id = cfg.get('telegram_bot_token'), cfg.get('telegram_chat_id')
    if not token or not chat_id:
        raise RuntimeError('Telegram token or chat ID is missing')
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f'https://api.telegram.org/bot{token}/sendMessage', json={
            'chat_id': chat_id,
            'text': 'JobTrack: Telegram connection test successful.',
        })
        response.raise_for_status()
    return True


def test_email(cfg: dict) -> bool:
    sample = Job(source='test', external_id='test', title='Connection Test', company='JobTrack', location='Berlin', url='https://example.com', score=100, reasons=['SMTP connection test'])
    return send_email([sample], cfg)
