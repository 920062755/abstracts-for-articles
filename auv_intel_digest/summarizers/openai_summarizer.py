from __future__ import annotations

import json
import os

import httpx

from auv_intel_digest.summarizers.base import SummaryResult
from auv_intel_digest.summarizers.noop import NoopSummarizer


class OpenAISummarizer:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("AUV_INTEL_LLM_MODEL", "gpt-4o-mini")
        self.http_client = http_client
        self.warnings: list[str] = []
        if not self.api_key:
            self.warnings.append("OPENAI_API_KEY 未配置，已回退为 noop 中文摘要。")
        self._fallback = NoopSummarizer(self.warnings[0] if self.warnings else None)

    def summarize_item(self, item) -> SummaryResult:
        if not self.api_key:
            return self._fallback.summarize_item(item)

        client = self.http_client or httpx.Client(timeout=30)
        close_client = self.http_client is None
        try:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是科研资讯摘要助手。请只输出 JSON，字段包括 "
                                "zh_title, zh_summary, key_points, risks, opportunities, "
                                "follow_ups, importance。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"标题：{item.title}\n"
                                f"来源：{item.source}\n"
                                f"链接：{item.link}\n"
                                f"摘要：{item.summary or ''}"
                            ),
                        },
                    ],
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return self._parse_result(content)
        except Exception as exc:
            warning = f"OpenAI 摘要失败，已回退为 noop：{exc}"
            self.warnings.append(warning)
            fallback = NoopSummarizer(warning).summarize_item(item)
            fallback.warning = warning
            return fallback
        finally:
            if close_client:
                client.close()

    def _parse_result(self, content: str) -> SummaryResult:
        data = json.loads(content)
        return SummaryResult(
            zh_title=str(data.get("zh_title") or ""),
            zh_summary=str(data.get("zh_summary") or ""),
            key_points=_as_list(data.get("key_points")),
            risks=_as_list(data.get("risks")),
            opportunities=_as_list(data.get("opportunities")),
            follow_ups=_as_list(data.get("follow_ups")),
            importance=str(data.get("importance") or "medium"),
        )


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
