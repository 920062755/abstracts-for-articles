import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from auv_intel_digest.cli import app
from auv_intel_digest.notifiers.telegram import (
    TelegramNotifier,
    build_telegram_message,
    split_telegram_message,
)


def test_telegram_notifier_sends_chunked_messages_with_mock_http():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "payload": json.loads(request.content.decode("utf-8")),
            }
        )
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(
        bot_token="test-token",
        chat_id="123456",
        max_chars=500,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    notifier.send(
        title="Daily Digest",
        markdown="\n".join([f"item {idx}" for idx in range(120)]),
        markdown_path=Path("digests/latest.zh.md"),
        json_path=Path("digests/latest.zh.json"),
    )

    assert len(requests) > 1
    assert all("test-token" in item["url"] for item in requests)
    assert all(item["payload"]["chat_id"] == "123456" for item in requests)
    assert all(len(item["payload"]["text"]) <= 500 for item in requests)


def test_telegram_notifier_requires_token_and_chat_id(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    notifier = TelegramNotifier()

    with pytest.raises(RuntimeError):
        notifier.send(
            title="title",
            markdown="body",
            markdown_path=Path("digests/latest.zh.md"),
            json_path=Path("digests/latest.zh.json"),
        )


def test_telegram_notifier_http_error_does_not_leak_bot_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False})

    notifier = TelegramNotifier(
        bot_token="secret-token",
        chat_id="123456",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError) as exc_info:
        notifier.send(
            title="title",
            markdown="body",
            markdown_path=Path("digests/latest.zh.md"),
            json_path=Path("digests/latest.zh.json"),
        )

    assert "401" in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)


def test_split_telegram_message_limits_chunk_size():
    chunks = split_telegram_message("a" * 1200, max_chars=500)

    assert len(chunks) == 3
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_all_source_failure_digest_adds_telegram_warning():
    message = build_telegram_message(
        title="Daily Digest",
        markdown="# AUV Intel Digest\n\n- Run status: all sources failed\n",
        markdown_path=Path("digests/latest.zh.md"),
        json_path=Path("digests/latest.zh.json"),
    )

    assert "AUV" in message
    assert "failed" in message.lower()


def test_send_telegram_cli_smoke(monkeypatch):
    calls = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return 2

    monkeypatch.setattr("auv_intel_digest.cli.send_markdown_file_via_telegram", fake_send)
    result = CliRunner().invoke(
        app,
        [
            "send-telegram",
            "--markdown",
            "digests/latest.zh.md",
            "--title",
            "Daily Digest",
            "--max-chars",
            "1000",
        ],
    )

    assert result.exit_code == 0
    assert "Telegram: sent 2 message chunk(s)" in result.output
    assert calls[0]["title"] == "Daily Digest"
    assert calls[0]["max_chars"] == 1000


def test_send_telegram_cli_skips_when_secrets_missing(monkeypatch):
    base = Path("tests/.tmp/telegram")
    base.mkdir(parents=True, exist_ok=True)
    markdown = base / "latest.zh.md"
    markdown.write_text("# AUV Digest\n", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = CliRunner().invoke(app, ["send-telegram", "--markdown", str(markdown)])

    assert result.exit_code == 0
    assert "Telegram: skipped" in result.output


def test_deployment_check_cli_does_not_leak_secret_values(monkeypatch):
    base = Path("tests/.tmp/deployment_check")
    base.mkdir(parents=True, exist_ok=True)
    sources = base / "sources.json"
    state_dir = base / "state"
    output_dir = base / "digests"
    sources.write_text('{"sources": []}', encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "secret-chat")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai")
    monkeypatch.setenv("SMTP_PASSWORD", "secret-smtp")

    result = CliRunner().invoke(
        app,
        [
            "deployment-check",
            "--sources",
            str(sources),
            "--state-dir",
            str(state_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "telegram_bot_token: present" in result.output
    assert "telegram_chat_id: present" in result.output
    assert "openai_api_key: present" in result.output
    assert "smtp_password: present" in result.output
    assert "secret-token" not in result.output
    assert "secret-chat" not in result.output
    assert "secret-openai" not in result.output
    assert "secret-smtp" not in result.output
