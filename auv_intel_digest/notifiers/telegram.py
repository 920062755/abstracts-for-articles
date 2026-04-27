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
        parse_mode: str | None = None,
        disable_web_page_preview: bool = True,
        max_chars: int = 3800,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.bot_token = bot_token if bot_token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", "")
        self.parse_mode = parse_mode if parse_mode is not None else os.getenv("TELEGRAM_PARSE_MODE", "")
        self.disable_web_page_preview = disable_web_page_preview
        self.max_chars = max(500, min(max_chars, 4096))
        self.http_client = http_client

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("Telegram bot token or chat ID is not configured.")

        message = build_telegram_message(
            title=title,
            markdown=markdown,
            markdown_path=markdown_path,
            json_path=json_path,
            html_path=html_path,
        )
        for chunk in split_telegram_message(message, self.max_chars):
            self._send_message(chunk)

    def _send_message(self, message: str) -> None:
        client = self.http_client or httpx.Client(timeout=20)
        close_client = self.http_client is None
        payload: dict[str, object] = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": self.disable_web_page_preview,
        }
        if self.parse_mode:
            payload["parse_mode"] = self.parse_mode
        try:
            response = client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise RuntimeError(f"Telegram send failed with HTTP status {status_code}.") from None
        except httpx.RequestError as exc:
            raise RuntimeError(f"Telegram send failed with {exc.__class__.__name__}.") from None
        finally:
            if close_client:
                client.close()


def build_telegram_message(
    *,
    title: str,
    markdown: str,
    markdown_path: Path,
    json_path: Path,
    html_path: Path | None = None,
) -> str:
    lines = [
        title,
        "",
        markdown.strip(),
        "",
        f"Markdown: {markdown_path}",
        f"JSON: {json_path}",
    ]
    if html_path:
        lines.append(f"HTML: {html_path}")
    return "\n".join(lines).strip()


def split_telegram_message(message: str, max_chars: int = 3800) -> list[str]:
    max_chars = max(500, min(max_chars, 4096))
    if len(message) <= max_chars:
        return [message]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in message.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current).rstrip())
            current = []
            current_len = 0
        if line_len > max_chars:
            if current:
                chunks.append("\n".join(current).rstrip())
                current = []
                current_len = 0
            for start in range(0, len(line), max_chars):
                chunks.append(line[start : start + max_chars])
            continue
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current).rstrip())
    return chunks


def send_markdown_file_via_telegram(
    *,
    markdown_path: Path,
    title: str,
    json_path: Path | None = None,
    html_path: Path | None = None,
    max_chars: int | None = None,
    notifier: TelegramNotifier | None = None,
) -> int:
    markdown = markdown_path.read_text(encoding="utf-8")
    selected_json_path = json_path or markdown_path.with_suffix(".json")
    selected_max_chars = max_chars
    if selected_max_chars is None:
        selected_max_chars = int(os.getenv("TELEGRAM_MAX_CHARS", "3800") or "3800")
    selected_notifier = notifier or TelegramNotifier(max_chars=selected_max_chars)
    selected_notifier.send(
        title=title,
        markdown=markdown,
        markdown_path=markdown_path,
        json_path=selected_json_path,
        html_path=html_path,
    )
    return len(
        split_telegram_message(
            build_telegram_message(
                title=title,
                markdown=markdown,
                markdown_path=markdown_path,
                json_path=selected_json_path,
                html_path=html_path,
            ),
            selected_max_chars,
        )
    )
