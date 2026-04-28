from __future__ import annotations

import os
from pathlib import Path

import httpx

from auv_intel_digest.notifiers.base import Notifier


class TelegramNotifier(Notifier):
    name = "telegram"

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
        max_chars: int = 3800,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.bot_token = bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", "")
        self.max_chars = max(500, min(max_chars, 4096))
        self.http_client = http_client

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

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
            raise RuntimeError("Telegram bot token or chat ID is not configured.")
        message = "\n\n".join([title, markdown.strip(), f"Markdown: {markdown_path}", f"JSON: {json_path}"])
        for chunk in _split_message(message, self.max_chars):
            self._send_message(chunk)

    def _send_message(self, message: str) -> None:
        client = self.http_client or httpx.Client(timeout=20)
        close_client = self.http_client is None
        try:
            response = client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "disable_web_page_preview": True},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise RuntimeError(f"Telegram send failed with HTTP status {status_code}.") from None
        finally:
            if close_client:
                client.close()


def send_markdown_file_via_telegram(
    *,
    markdown_path: Path,
    title: str,
    json_path: Path | None = None,
    notifier: TelegramNotifier | None = None,
) -> int:
    selected = notifier or TelegramNotifier()
    if not selected.is_configured():
        return 0
    markdown = markdown_path.read_text(encoding="utf-8")
    selected.send(
        title=title,
        markdown=markdown,
        markdown_path=markdown_path,
        json_path=json_path or markdown_path.with_suffix(".json"),
    )
    return 1


def _split_message(message: str, max_chars: int) -> list[str]:
    return [message[start : start + max_chars] for start in range(0, len(message), max_chars)]
