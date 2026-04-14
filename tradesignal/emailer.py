from __future__ import annotations

from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path
import os
import re
import smtplib
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import EmailNotificationConfig


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
ASIA_SHANGHAI = ZoneInfo("Asia/Shanghai")
SMTP_TIMEOUT_SECONDS = 90


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
    delays = [0, 2, 5]
    last_error: Exception | None = None
    for attempt, delay_seconds in enumerate(delays, start=1):
        if delay_seconds:
            time.sleep(delay_seconds)
        try:
            _send_message_once(config, password=password, message=message)
            return
        except (smtplib.SMTPException, OSError) as exc:
            last_error = exc
            if attempt == len(delays):
                break
            print(
                f"EMAIL_RETRY attempt={attempt} next_delay_seconds={delays[attempt]} error={exc}",
                file=sys.stderr,
                flush=True,
            )
    raise RuntimeError(f"email delivery failed after {len(delays)} attempts: {last_error}") from last_error


def _send_message_once(config: EmailNotificationConfig, *, password: str, message: EmailMessage) -> None:
    with _build_smtp_client(config) as smtp:
        smtp.ehlo()
        if config.use_tls and not config.use_ssl:
            smtp.starttls()
            smtp.ehlo()
        if config.username:
            smtp.login(config.username, password)
        smtp.send_message(message)


def _build_smtp_client(config: EmailNotificationConfig):
    if not config.smtp_proxy_host:
        smtp_factory = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
        return smtp_factory(config.smtp_host, config.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)

    if config.smtp_proxy_port is None:
        raise ValueError("notification.email.smtp_proxy_port is required when smtp_proxy_host is set")

    smtp_factory = _ProxySMTP_SSL if config.use_ssl else _ProxySMTP
    return smtp_factory(
        config.smtp_host,
        config.smtp_port,
        timeout=SMTP_TIMEOUT_SECONDS,
        proxy_host=config.smtp_proxy_host,
        proxy_port=config.smtp_proxy_port,
    )


def _create_proxy_socket(*, host: str, port: int, timeout: float | None, proxy_host: str, proxy_port: int):
    try:
        import socks
    except ModuleNotFoundError as exc:
        raise RuntimeError("PySocks is required when notification.email.smtp_proxy_host is configured") from exc

    if timeout is not None and timeout <= 0:
        raise ValueError("Non-blocking sockets are not supported for proxied SMTP connections")

    return socks.create_connection(
        (host, port),
        timeout=timeout,
        proxy_type=socks.SOCKS5,
        proxy_addr=proxy_host,
        proxy_port=proxy_port,
    )


class _ProxySMTP(smtplib.SMTP):
    def __init__(self, *args, proxy_host: str, proxy_port: int, **kwargs):
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        super().__init__(*args, **kwargs)

    def _get_socket(self, host, port, timeout):
        if self.debuglevel > 0:
            self._print_debug("connect via socks5 proxy", (self._proxy_host, self._proxy_port))
        return _create_proxy_socket(
            host=host,
            port=port,
            timeout=timeout,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
        )


class _ProxySMTP_SSL(smtplib.SMTP_SSL):
    def __init__(self, *args, proxy_host: str, proxy_port: int, **kwargs):
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        super().__init__(*args, **kwargs)

    def _get_socket(self, host, port, timeout):
        if self.debuglevel > 0:
            self._print_debug("connect via socks5 proxy", (self._proxy_host, self._proxy_port))
        proxied_socket = _create_proxy_socket(
            host=host,
            port=port,
            timeout=timeout,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
        )
        return self.context.wrap_socket(proxied_socket, server_hostname=self._host)


def write_email_preview(config: EmailNotificationConfig, *, subject: str, body: str, html_body: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(ASIA_SHANGHAI).strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_{_sanitize_filename(subject)[:80] or 'tradesignal'}.html"
    preview_path = OUTPUT_DIR / filename
    preview_path.write_text(build_preview_document(subject=subject, html_body=html_body), encoding="utf-8")
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
            "  </style>",
            "</head>",
            "<body>",
            f"{html_body}",
            "</body>",
            "</html>",
        ]
    )


def build_preview_document(*, subject: str, html_body: str) -> str:
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
