from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from auv_intel_digest.notifiers.base import Notifier


class EmailNotifier(Notifier):
    name = "email"

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        email_from: str | None = None,
        email_to: str | None = None,
        use_ssl: bool | None = None,
        timeout: float = 20,
        smtp_ssl_factory=None,
        smtp_factory=None,
    ) -> None:
        self.smtp_host = smtp_host if smtp_host is not None else os.getenv("SMTP_HOST", "")
        self.smtp_port = smtp_port if smtp_port is not None else int(os.getenv("SMTP_PORT", "465") or "465")
        self.smtp_username = (
            smtp_username if smtp_username is not None else os.getenv("SMTP_USERNAME", "")
        )
        self.smtp_password = (
            smtp_password if smtp_password is not None else os.getenv("SMTP_PASSWORD", "")
        )
        self.email_from = email_from if email_from is not None else os.getenv("EMAIL_FROM", "")
        self.email_to = email_to if email_to is not None else os.getenv("EMAIL_TO", "920062755@qq.com")
        self.use_ssl = use_ssl if use_ssl is not None else _bool_env("EMAIL_USE_SSL", True)
        self.timeout = timeout
        self.smtp_ssl_factory = smtp_ssl_factory or smtplib.SMTP_SSL
        self.smtp_factory = smtp_factory or smtplib.SMTP

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password and self.email_to)

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        if not self.is_configured():
            raise RuntimeError("Email SMTP host, username, password, or recipient is not configured.")

        message = build_email_message(
            title=title,
            markdown=markdown,
            markdown_path=markdown_path,
            json_path=json_path,
            html_path=html_path,
            email_from=self.email_from or self.smtp_username,
            email_to=self.email_to,
        )
        client_cls = self.smtp_ssl_factory if self.use_ssl else self.smtp_factory
        with client_cls(self.smtp_host, self.smtp_port, timeout=self.timeout) as smtp:
            if not self.use_ssl:
                smtp.starttls()
            smtp.login(self.smtp_username, self.smtp_password)
            smtp.send_message(message)


def build_email_message(
    *,
    title: str,
    markdown: str,
    markdown_path: Path,
    json_path: Path,
    html_path: Path | None,
    email_from: str,
    email_to: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = title
    message["From"] = email_from
    message["To"] = email_to
    body = "\n".join(
        [
            markdown.strip(),
            "",
            f"Markdown: {markdown_path}",
            f"JSON: {json_path}",
            f"HTML: {html_path}" if html_path else "",
        ]
    ).strip()
    message.set_content(body, subtype="plain", charset="utf-8")
    return message


def send_markdown_file_via_email(
    *,
    markdown_path: Path,
    title: str,
    json_path: Path | None = None,
    html_path: Path | None = None,
    notifier: EmailNotifier | None = None,
) -> bool:
    selected_notifier = notifier or EmailNotifier()
    if not selected_notifier.is_configured():
        return False
    markdown = markdown_path.read_text(encoding="utf-8")
    selected_notifier.send(
        title=title,
        markdown=markdown,
        markdown_path=markdown_path,
        json_path=json_path or markdown_path.with_suffix(".json"),
        html_path=html_path,
    )
    return True


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
