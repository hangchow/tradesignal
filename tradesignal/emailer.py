from __future__ import annotations

from email.message import EmailMessage
import os
import smtplib

from .config import EmailNotificationConfig


def send_email_notification(config: EmailNotificationConfig, *, subject: str, body: str) -> None:
    if not config.enabled:
        return
    if not config.smtp_host:
        raise ValueError("notification.email.smtp_host is required when email is enabled")
    if not config.from_address:
        raise ValueError("notification.email.from is required when email is enabled")
    if not config.to_addresses:
        raise ValueError("notification.email.to must contain at least one address when email is enabled")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_address
    message["To"] = ", ".join(config.to_addresses)
    message.set_content(body)

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
