from pathlib import Path

from typer.testing import CliRunner

from auv_intel_digest.cli import app


def test_send_telegram_cli_skips_when_secret_missing(monkeypatch):
    markdown = Path("tests/.tmp/telegram/latest.zh.md")
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("# AUV 情报摘要", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = CliRunner().invoke(app, ["send-telegram", "--markdown", str(markdown)])

    assert result.exit_code == 0
    assert "Telegram: skipped" in result.output
