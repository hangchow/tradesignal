from __future__ import annotations

from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
import os
import re
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import EmailNotificationConfig


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")


def send_email_notification(config: EmailNotificationConfig, *, subject: str, body: str, html_body: str) -> None:
    if not config.enabled:
        return
    if not config.smtp_host:
        raise ValueError("notification.email.smtp_host is required when email is enabled")
    if not config.from_address:
        raise ValueError("notification.email.from is required when email is enabled")
    if not config.to_addresses:
        raise ValueError("notification.email.to must contain at least one address when email is enabled")

    message = build_email_message(config, subject=subject, body=body, html_body=html_body)

    password = config.password or (os.environ.get(config.password_env, "") if config.password_env else "")
    smtp_factory = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
    with smtp_factory(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        if config.use_tls and not config.use_ssl:
            smtp.starttls()
            smtp.ehlo()
        if config.username:
            smtp.login(config.username, password)
        smtp.send_message(message)


def write_email_preview(config: EmailNotificationConfig, *, subject: str, body: str, html_body: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(ASIA_SHANGHAI).strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_{_sanitize_filename(subject)[:80] or 'tradesignal'}.html"
    preview_path = OUTPUT_DIR / filename
    preview_path.write_text(build_html_document(subject=subject, html_body=html_body), encoding="utf-8")
    return preview_path


def build_email_message(config: EmailNotificationConfig, *, subject: str, body: str, html_body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    if config.from_name:
        message["From"] = formataddr((str(Header(config.from_name, "utf-8")), config.from_address or ""))
    else:
        message["From"] = config.from_address or ""
    message["To"] = ", ".join(config.to_addresses)
    message.set_content(body)
    message.add_alternative(build_html_document(subject=subject, html_body=html_body), subtype="html")
    return message


def _sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")


def build_html_document(*, subject: str, html_body: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="zh-CN">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{escape(subject)}</title>",
            "  <style>",
            "    body { margin: 0; background: #f4f1ea; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1f2937; }",
            "    .preview-shell { padding: 24px 16px; }",
            "    .preview-card { max-width: 760px; margin: 0 auto; background: #fffdf8; border: 1px solid #e7decf; border-radius: 18px; overflow: hidden; box-shadow: 0 18px 50px rgba(74, 52, 29, 0.08); }",
            "    .preview-bar { padding: 14px 18px; background: linear-gradient(135deg, #f3e4c8, #efe9dd); border-bottom: 1px solid #e7decf; font-size: 13px; color: #6b5b45; }",
            "  </style>",
            "</head>",
            "<body>",
            '  <div class="preview-shell">',
            '    <div class="preview-card">',
            f'      <div class="preview-bar">邮件预览: {escape(subject)}</div>',
            f"      {html_body}",
            "    </div>",
            "  </div>",
            "</body>",
            "</html>",
        ]
    )
