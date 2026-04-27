from __future__ import annotations

from pathlib import Path

import httpx

from auv_intel_digest.models import DailyDigest
from auv_intel_digest.notifiers.base import Notifier
from auv_intel_digest.reports.markdown import selected_by_topic, top_items


def build_qq_summary(
    digest: DailyDigest,
    markdown_path: Path,
    html_path: Path | None,
    max_items_per_topic: int,
) -> str:
    selected = selected_by_topic(digest.items, digest.topics, max_items_per_topic)
    lines = [
        f"AUV/UUV 科研资讯日报 - {digest.report_date.isoformat()}",
        f"今日总条目数：{len(digest.items)}",
        "每个主题精选条目数：",
    ]
    for topic in digest.topics:
        lines.append(f"- {topic.name_zh}：{len(selected[topic.key])}")

    lines.append("今日最值得关注的 3 条：")
    for idx, item in enumerate(top_items(digest.items, 3), start=1):
        lines.append(f"{idx}. {item.title} ({item.source}, {item.score:.2f})")

    lines.append(f"Markdown 报告路径：{markdown_path}")
    if html_path:
        lines.append(f"HTML 报告路径：{html_path}")
    return "\n".join(lines)


class QQOneBotNotifier(Notifier):
    name = "qq_onebot"

    def __init__(
        self,
        endpoint: str,
        access_token: str,
        target_type: str,
        target_id: str,
        push_mode: str = "summary",
        push_max_chars: int = 3500,
        digest: DailyDigest | None = None,
        max_items_per_topic: int = 5,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.access_token = access_token
        self.target_type = target_type
        self.target_id = target_id
        self.push_mode = push_mode
        self.push_max_chars = push_max_chars
        self.digest = digest
        self.max_items_per_topic = max_items_per_topic

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        if not self.endpoint or not self.target_id:
            raise RuntimeError("QQ OneBot endpoint or target ID is not configured.")

        message = markdown
        if self.push_mode != "full" or len(markdown) > self.push_max_chars:
            if not self.digest:
                message = f"{title}\nMarkdown 报告路径：{markdown_path}\nJSON 路径：{json_path}"
            else:
                message = build_qq_summary(
                    self.digest, markdown_path, html_path, self.max_items_per_topic
                )

        if len(message) > self.push_max_chars:
            message = message[: self.push_max_chars - 30] + "\n...内容过长，已截断。"

        if self.push_mode == "full" and len(markdown) <= self.push_max_chars:
            self._send_message(message)
            return

        self._send_message(message)

    def _send_message(self, message: str) -> None:
        action = "send_private_msg" if self.target_type == "private" else "send_group_msg"
        id_key = "user_id" if self.target_type == "private" else "group_id"
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        response = httpx.post(
            f"{self.endpoint}/{action}",
            json={id_key: self.target_id, "message": message},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
