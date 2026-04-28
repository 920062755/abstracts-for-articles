from pathlib import Path

from typer.testing import CliRunner

from auv_intel_digest.cli import app
from auv_intel_digest.notifiers.email import (
    EmailNotifier,
    build_email_message,
    send_markdown_file_via_email,
)


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=20):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged_in = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        return None

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.messages.append(message)


def test_email_notifier_sends_with_mock_smtp():
    FakeSMTP.instances.clear()
    notifier = EmailNotifier(
        smtp_host="smtp.qq.com",
        smtp_port=465,
        smtp_username="920062755@qq.com",
        smtp_password="auth-code",
        email_from="920062755@qq.com",
        email_to="920062755@qq.com",
        smtp_ssl_factory=FakeSMTP,
    )

    notifier.send(
        title="AUV 情报摘要",
        markdown="# AUV 情报摘要",
        markdown_path=Path("digests/latest.zh.md"),
        json_path=Path("digests/latest.zh.json"),
    )

    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.qq.com"
    assert smtp.logged_in == ("920062755@qq.com", "auth-code")
    assert smtp.messages[0]["To"] == "920062755@qq.com"


def test_send_email_returns_false_when_smtp_missing(monkeypatch):
    markdown = Path("tests/.tmp/email/latest-missing.zh.md")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("# AUV 情报摘要", encoding="utf-8")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    assert send_markdown_file_via_email(markdown_path=markdown, title="AUV 情报摘要") is False


def test_email_message_omits_missing_json_path():
    markdown = Path("tests/.tmp/email/latest-no-json.zh.md")
    json_path = Path("tests/.tmp/email/latest-no-json.zh.json")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("# AUV Digest", encoding="utf-8")
    if json_path.exists():
        json_path.unlink()

    message = build_email_message(
        title="AUV Digest",
        markdown="# AUV Digest",
        markdown_path=markdown,
        json_path=json_path,
        html_path=None,
        email_from="sender@example.test",
        email_to="receiver@example.test",
    )

    body = message.get_content()
    assert f"Markdown: {markdown}" in body
    assert "JSON:" not in body


def test_send_email_cli_skips_when_smtp_missing(monkeypatch):
    markdown = Path("tests/.tmp/email/latest.zh.md")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("# AUV 情报摘要", encoding="utf-8")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    result = CliRunner().invoke(app, ["send-email", "--markdown", str(markdown)])

    assert result.exit_code == 0
    assert "Email: skipped" in result.output


def test_deployment_check_reports_email_secrets_without_leaking_values(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("SMTP_USERNAME", "920062755@qq.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret-auth-code")

    result = CliRunner().invoke(app, ["deployment-check"])

    assert result.exit_code == 0
    assert "smtp_host: present" in result.output
    assert "smtp_username: present" in result.output
    assert "smtp_password: present" in result.output
    assert "secret-auth-code" not in result.output
