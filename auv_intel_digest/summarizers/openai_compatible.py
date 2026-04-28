from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from auv_intel_digest.summarizers.base import SummaryResult
from auv_intel_digest.summarizers.noop import NoopSummarizer


@dataclass
class LLMResponseError(Exception):
    error_type: str
    status_code: int | None = None
    content_type: str | None = None
    preview: str | None = None

    def __str__(self) -> str:
        parts = [self.error_type]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.content_type:
            parts.append(f"content_type={self.content_type}")
        if self.preview:
            parts.append(f"preview={self.preview}")
        return " ".join(parts)


class OpenAICompatibleSummarizer:
    name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        fallback_models: list[str] | str | None = None,
        timeout: float | None = None,
        max_items: int | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else _env_first("AUV_INTEL_LLM_API_KEY", "OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("AUV_INTEL_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("AUV_INTEL_LLM_MODEL", "gpt-4o-mini")
        self.fallback_models = _parse_models(
            fallback_models
            if fallback_models is not None
            else os.getenv("AUV_INTEL_LLM_FALLBACK_MODELS", "")
        )
        self.timeout = timeout if timeout is not None else _float_env("AUV_INTEL_LLM_TIMEOUT", 60)
        self.max_items = max_items if max_items is not None else _int_env("AUV_INTEL_LLM_MAX_ITEMS", 0)
        self.http_client = http_client
        self.warnings: list[str] = []
        self._llm_items_used = 0
        if not self.api_key:
            self.warnings.append("AUV_INTEL_LLM_API_KEY/OPENAI_API_KEY 未配置，已回退为 noop 中文摘要。")
        self._fallback = NoopSummarizer(self.warnings[0] if self.warnings else None)

    def summarize_item(self, item) -> SummaryResult:
        if not self.api_key:
            return self._fallback.summarize_item(item)

        if self.max_items > 0 and self._llm_items_used >= self.max_items:
            warning = f"LLM 摘要条目数已达到上限 {self.max_items}，后续条目已回退为 noop。"
            self._warn_once(warning)
            fallback = NoopSummarizer(warning).summarize_item(item)
            fallback.warning = warning
            return fallback

        self._llm_items_used += 1
        client = self.http_client or httpx.Client(timeout=httpx.Timeout(self.timeout))
        close_client = self.http_client is None
        attempt_errors: list[str] = []
        try:
            for model in self._candidate_models():
                try:
                    content = self._request_summary(client, item, model)
                    result = self._parse_result(content)
                    if model != self.model:
                        self._warn_once(
                            f"OpenAI-compatible 主模型失败，已使用备用模型 {model}；"
                            f"之前失败：{'; '.join(attempt_errors)}"
                        )
                    return result
                except Exception as exc:
                    attempt_errors.append(_format_attempt_error(model, exc))
            warning = "OpenAI-compatible 摘要失败，已回退为 noop：" + "; ".join(attempt_errors)
            self.warnings.append(warning)
            fallback = NoopSummarizer(warning).summarize_item(item)
            fallback.warning = warning
            return fallback
        finally:
            if close_client:
                client.close()

    def _candidate_models(self) -> list[str]:
        models = [self.model, *self.fallback_models]
        deduped: list[str] = []
        for model in models:
            if model and model not in deduped:
                deduped.append(model)
        return deduped

    def _request_summary(self, client: httpx.Client, item, model: str) -> str:
        response = client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是科研资讯摘要助手。只输出 JSON，字段包括 "
                            "zh_title, zh_summary, key_points, risks, opportunities, "
                            "follow_ups, importance。不要输出 Markdown。"
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
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            raise
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMResponseError(
                "response_JSONDecodeError",
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                preview=_preview(response.text),
            ) from exc
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                "response_schema_error",
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                preview=_preview(json.dumps(payload, ensure_ascii=False)),
            ) from exc

    def _parse_result(self, content: str) -> SummaryResult:
        try:
            data = json.loads(_json_candidate(content))
        except ValueError as exc:
            raise LLMResponseError("model_JSONDecodeError", preview=_preview(content)) from exc
        return SummaryResult(
            zh_title=str(data.get("zh_title") or ""),
            zh_summary=str(data.get("zh_summary") or ""),
            key_points=_as_list(data.get("key_points")),
            risks=_as_list(data.get("risks")),
            opportunities=_as_list(data.get("opportunities")),
            follow_ups=_as_list(data.get("follow_ups")),
            importance=str(data.get("importance") or "medium"),
        )

    def _warn_once(self, warning: str) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)


def _format_attempt_error(model: str, exc: Exception) -> str:
    if isinstance(exc, LLMResponseError):
        return f"{model}: {exc}"
    if isinstance(exc, httpx.TimeoutException):
        return f"{model}: timeout {exc.__class__.__name__}"
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        return (
            f"{model}: http_error status={response.status_code} "
            f"preview={_preview(response.text)}"
        )
    if isinstance(exc, httpx.RequestError):
        return f"{model}: network_error {exc.__class__.__name__}"
    return f"{model}: {exc.__class__.__name__}"


def _json_candidate(content: str) -> str:
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _preview(value: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _parse_models(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = value.split(",")
    return [item.strip() for item in raw if item.strip()]


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""
