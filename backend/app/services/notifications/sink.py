"""Best-effort notification sink. Never raises into the detection path."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("egreen.notify")

_NOTIFY_SEVERITIES = {"critical", "high"}


async def notify_alert(
    *, title: str, severity: str, risk_score: float, rule_codes: list[str]
) -> None:
    if not settings.notify_high_severity or severity not in _NOTIFY_SEVERITIES:
        return
    text = (
        f":rotating_light: *{severity.upper()}* alert — {title}\n"
        f"risk {risk_score} · rules {', '.join(rule_codes)}"
    )
    if settings.slack_webhook:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(settings.slack_webhook, json={"text": text})
        except httpx.HTTPError as exc:
            log.warning("slack_notify_failed", error=str(exc))

    if settings.smtp_host and settings.notify_email_to:
        try:
            await asyncio.to_thread(_send_email, title, text)
        except (smtplib.SMTPException, OSError) as exc:
            log.warning("email_notify_failed", error=str(exc))


def _send_email(subject: str, body: str) -> None:
    host = settings.smtp_host
    if not host or not settings.notify_email_to:
        return
    msg = EmailMessage()
    msg["Subject"] = f"[Egreen Quanta] {subject}"
    msg["From"] = settings.smtp_from
    msg["To"] = settings.notify_email_to
    msg.set_content(body)
    with smtplib.SMTP(host, settings.smtp_port, timeout=8) as s:
        s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password or "")
        s.send_message(msg)
