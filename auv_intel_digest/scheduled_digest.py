from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from auv_intel_digest.summarizers import SummaryResult, build_summarizer


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    category: str | None = None
    enabled: bool = True


@dataclass
class FeedItem:
    item_id: str
    title: str
    link: str
    source: str
    published: str | None = None
    summary: str | None = None
    guid: str | None = None
    category: str | None = None
    seen: bool = False


@dataclass
class FeedSourceResult:
    source: FeedSource
    status: str
    items: list[FeedItem] = field(default_factory=list)
    error: str | None = None
    error_type: str | None = None
    diagnostic: str | None = None


@dataclass
class ScheduledDigestResult:
    generated_at: str
    sources_checked: int
    successful: int
    failed: int
    new_items: int
    output_limit: int
    output_path: Path
    items: list[FeedItem]
    source_results: list[FeedSourceResult]
    language: str = "en"
    summarizer_name: str = "noop"
    summaries: dict[str, SummaryResult] = field(default_factory=dict)
    summary_warnings: list[str] = field(default_factory=list)


@dataclass
class SourceDiagnostic:
    name: str
    url: str
    enabled: bool
    category: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    byte_count: int = 0
    parseable: bool = False
    item_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    diagnostic: str | None = None


def load_feed_sources(path: str | Path) -> list[FeedSource]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sources_data = data.get("sources", data if isinstance(data, list) else [])
    return [
        FeedSource(
            name=entry["name"],
            url=entry["url"],
            category=entry.get("category"),
            enabled=bool(entry.get("enabled", True)),
        )
        for entry in sources_data
    ]


def stable_item_id(*, link: str, guid: str | None, title: str) -> str:
    basis = guid or link or title
    return hashlib.sha256(basis.strip().casefold().encode("utf-8")).hexdigest()[:24]


def parse_feed(xml_text: str, source: FeedSource) -> list[FeedItem]:
    root = ET.fromstring(xml_text)
    tag = _local_name(root.tag)
    if tag == "rss":
        return _parse_rss(root, source)
    if tag == "feed":
        return _parse_atom(root, source)
    raise ValueError(f"Unsupported feed root: {tag}")


def collect_feed_sources(
    sources: list[FeedSource],
    *,
    timeout: float = 20,
    user_agent: str = "auv_intel_digest/0.6",
    http_client: httpx.Client | None = None,
) -> list[FeedSourceResult]:
    results: list[FeedSourceResult] = []
    client = http_client or httpx.Client(timeout=timeout, headers={"User-Agent": user_agent})
    close_client = http_client is None
    try:
        for source in [source for source in sources if source.enabled]:
            try:
                response = client.get(source.url)
                response.raise_for_status()
                items = parse_feed(response.text, source)
                results.append(FeedSourceResult(source=source, status="ok", items=items))
            except Exception as exc:
                results.append(
                    FeedSourceResult(
                        source=source,
                        status="error",
                        items=[],
                        error=str(exc),
                        error_type=classify_collection_error(exc),
                        diagnostic=diagnose_collection_error(exc),
                    )
                )
    finally:
        if close_client:
            client.close()
    return results


def check_feed_sources(
    sources: list[FeedSource],
    *,
    timeout: float = 20,
    user_agent: str = "auv_intel_digest/0.6 check-sources",
    http_client: httpx.Client | None = None,
) -> list[SourceDiagnostic]:
    diagnostics: list[SourceDiagnostic] = []
    client = http_client or httpx.Client(timeout=timeout, headers={"User-Agent": user_agent})
    close_client = http_client is None
    try:
        for source in sources:
            diagnostic: SourceDiagnostic | None = None
            if not source.enabled:
                diagnostics.append(
                    SourceDiagnostic(
                        name=source.name,
                        url=source.url,
                        enabled=False,
                        category=source.category,
                        error_type="disabled",
                        error_message="Source is disabled; network check skipped.",
                    )
                )
                continue

            try:
                response = client.get(source.url)
                content = response.content
                diagnostic = SourceDiagnostic(
                    name=source.name,
                    url=source.url,
                    enabled=True,
                    category=source.category,
                    http_status=response.status_code,
                    content_type=response.headers.get("content-type"),
                    byte_count=len(content),
                )
                response.raise_for_status()
                items = parse_feed(response.text, source)
                diagnostic.parseable = True
                diagnostic.item_count = len(items)
                diagnostics.append(diagnostic)
            except Exception as exc:
                if diagnostic is None:
                    diagnostic = SourceDiagnostic(
                        name=source.name,
                        url=source.url,
                        enabled=True,
                        category=source.category,
                    )
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    diagnostic.http_status = exc.response.status_code
                    diagnostic.content_type = exc.response.headers.get("content-type")
                    diagnostic.byte_count = len(exc.response.content)
                diagnostic.error_type = classify_collection_error(exc)
                diagnostic.error_message = str(exc)
                diagnostic.diagnostic = diagnose_collection_error(exc)
                diagnostics.append(diagnostic)
    finally:
        if close_client:
            client.close()
    return diagnostics


def load_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {"seen": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(path: str | Path, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_seen(items: list[FeedItem], state: dict[str, Any], generated_at: str) -> None:
    seen = state.setdefault("seen", {})
    for item in items:
        previous = seen.get(item.item_id)
        item.seen = previous is not None
        if previous is None:
            seen[item.item_id] = {
                "first_seen": generated_at,
                "last_seen": generated_at,
                "title": item.title,
                "link": item.link,
                "source": item.source,
            }
        else:
            previous["last_seen"] = generated_at


def render_scheduled_digest(result: ScheduledDigestResult) -> str:
    if result.language == "zh":
        return _render_scheduled_digest_zh(result)
    return _render_scheduled_digest_en(result)


def all_sources_failed(result: ScheduledDigestResult) -> bool:
    return result.sources_checked > 0 and result.successful == 0 and result.failed > 0


def run_status_zh(result: ScheduledDigestResult) -> str:
    if all_sources_failed(result):
        return "全部失败"
    if result.successful > 0 and result.failed > 0:
        return "部分成功"
    if result.sources_checked == 0:
        return "无启用源"
    if result.successful > 0 and result.failed == 0 and result.new_items == 0:
        return "无新增"
    if result.new_items > 0:
        return "有新增"
    return "完成"


def _render_scheduled_digest_en(result: ScheduledDigestResult) -> str:
    lines = [
        "# AUV Intel Digest",
        "",
        f"Generated: {result.generated_at}",
        "",
        "## Run Summary",
        "",
        f"- Sources checked: {result.sources_checked}",
        f"- Successful: {result.successful}",
        f"- Failed: {result.failed}",
        f"- New items: {result.new_items}",
        f"- Run status: {run_status_zh(result)}",
        f"- Output limit: {result.output_limit}",
        "",
        "## Highlights",
        "",
    ]
    if not result.items:
        if all_sources_failed(result):
            lines.extend(
                [
                    "No valid intelligence digest was generated because all sources failed. "
                    "Check network access, proxy/firewall settings, RSS URLs, or runtime permissions.",
                    "",
                ]
            )
        else:
            lines.extend(["No new items found.", ""])
    for idx, item in enumerate(result.items, start=1):
        lines.extend(
            [
                f"### {idx}. {item.title}",
                "",
                f"- Source: {item.source}",
                f"- Published: {item.published or 'Unknown'}",
                f"- Link: {item.link or 'N/A'}",
                f"- Summary: {item.summary or 'No summary provided.'}",
                f"- Category: {item.category or 'Uncategorized'}",
                "- Suggested follow-up: Review the source item and decide whether it belongs in the daily research reading queue.",
                "",
            ]
        )
    _append_source_errors_en(lines, result)
    return "\n".join(lines).rstrip() + "\n"


def _render_scheduled_digest_zh(result: ScheduledDigestResult) -> str:
    lines = [
        "# AUV 情报摘要",
        "",
        f"生成时间：{result.generated_at}",
        "",
        "## 运行摘要",
        "",
        f"- 检查资讯源：{result.sources_checked}",
        f"- 成功：{result.successful}",
        f"- 失败：{result.failed}",
        f"- 新条目：{result.new_items}",
        f"- 运行状态：{run_status_zh(result)}",
        f"- 输出上限：{result.output_limit}",
        f"- 摘要器：{result.summarizer_name}",
        "",
    ]
    if result.summary_warnings:
        lines.extend(["摘要提示：", ""])
        for warning in result.summary_warnings:
            lines.append(f"- {warning}")
        lines.append("")
    lines.extend(["## 重点情报", ""])
    if not result.items:
        if all_sources_failed(result):
            lines.extend(
                [
                    "本次未生成有效情报摘要，因为所有资讯源采集失败。请先检查网络、代理、防火墙、RSS URL 或运行环境权限。",
                    "",
                ]
            )
        else:
            lines.extend(["今日暂无新条目。", ""])
    for idx, item in enumerate(result.items, start=1):
        summary = result.summaries.get(item.item_id)
        title = summary.zh_title if summary and summary.zh_title else item.title
        zh_summary = (
            summary.zh_summary
            if summary
            else "未启用 LLM 中文摘要，以下为原始摘要。" + (item.summary or "原始条目未提供摘要。")
        )
        lines.extend(
            [
                f"### {idx}. {title}",
                "",
                f"- 来源：{item.source}",
                f"- 发布时间：{item.published or '未知'}",
                f"- 链接：{item.link or 'N/A'}",
                f"- 原始标题：{item.title}",
                f"- 中文摘要：{zh_summary}",
                f"- 关键信息：{_join_zh_list(summary.key_points if summary else [])}",
                f"- 风险：{_join_zh_list(summary.risks if summary else [])}",
                f"- 机会：{_join_zh_list(summary.opportunities if summary else [])}",
                f"- 建议跟进：{_join_zh_list(summary.follow_ups if summary else [])}",
                "",
            ]
        )
    _append_source_errors_zh(lines, result)
    return "\n".join(lines).rstrip() + "\n"


def _append_source_errors_en(lines: list[str], result: ScheduledDigestResult) -> None:
    errors = [source for source in result.source_results if source.status != "ok"]
    lines.extend(["## Source Errors", ""])
    if not errors:
        lines.extend(["None.", ""])
    for error in errors:
        lines.append(f"- {error.source.name}:")
        lines.append(f"  - Error type: {error.error_type or 'unknown_error'}")
        lines.append(f"  - Raw error: {error.error or 'Unknown error'}")
        if error.diagnostic:
            lines.append(f"  - Explanation: {error.diagnostic}")


def _append_source_errors_zh(lines: list[str], result: ScheduledDigestResult) -> None:
    errors = [source for source in result.source_results if source.status != "ok"]
    lines.extend(["## 采集错误", ""])
    if not errors:
        lines.extend(["无。", ""])
    for error in errors:
        lines.append(f"- {error.source.name}:")
        lines.append(f"  - 错误类型：{error.error_type or 'unknown_error'}")
        lines.append(f"  - 原始错误：{error.error or '未知错误'}")
        if error.diagnostic:
            lines.append(f"  - 说明：{error.diagnostic}")


def write_scheduled_digest(path: str | Path, markdown: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")


def run_scheduled_digest(
    *,
    sources_path: str | Path,
    output_path: str | Path,
    limit: int,
    include_seen: bool = False,
    state_path: str | Path = ".auv_intel_digest/state.json",
    language: str = "en",
    summarizer_name: str = "noop",
    llm_model: str | None = None,
    summarizer=None,
    http_client: httpx.Client | None = None,
    fail_on_all_source_errors: bool = False,
) -> ScheduledDigestResult:
    generated_at = datetime.now().isoformat(timespec="minutes")
    sources = load_feed_sources(sources_path)
    enabled_sources = [source for source in sources if source.enabled]
    source_results = collect_feed_sources(enabled_sources, http_client=http_client)
    all_items = [item for result in source_results for item in result.items]
    sources_checked = len(enabled_sources)
    successful = sum(1 for result in source_results if result.status == "ok")
    failed = sum(1 for result in source_results if result.status != "ok")
    all_failed = sources_checked > 0 and successful == 0 and failed > 0
    if all_failed:
        selected: list[FeedItem] = []
        new_items = 0
    else:
        state = load_state(state_path)
        mark_seen(all_items, state, generated_at)
        write_state(state_path, state)
        selected = all_items if include_seen else [item for item in all_items if not item.seen]
        new_items = sum(1 for item in all_items if not item.seen)
    selected = sorted(selected, key=lambda item: item.published or "", reverse=True)[:limit]
    selected_summarizer = summarizer or build_summarizer(summarizer_name, llm_model=llm_model)
    summaries: dict[str, SummaryResult] = {}
    summary_warnings = list(getattr(selected_summarizer, "warnings", []))
    if language == "zh":
        for item in selected:
            summary = selected_summarizer.summarize_item(item)
            summaries[item.item_id] = summary
            if summary.warning:
                summary_warnings.append(summary.warning)
    result = ScheduledDigestResult(
        generated_at=generated_at,
        sources_checked=sources_checked,
        successful=successful,
        failed=failed,
        new_items=new_items,
        output_limit=limit,
        output_path=Path(output_path),
        items=selected,
        source_results=source_results,
        language=language,
        summarizer_name=getattr(selected_summarizer, "name", summarizer_name),
        summaries=summaries,
        summary_warnings=list(dict.fromkeys(summary_warnings)),
    )
    write_scheduled_digest(output_path, render_scheduled_digest(result))
    return result


def _parse_rss(root: ET.Element, source: FeedSource) -> list[FeedItem]:
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for entry in channel.findall("item"):
        title = clean_text(entry.findtext("title")) or "Untitled"
        link = clean_text(entry.findtext("link")) or ""
        guid = clean_text(entry.findtext("guid"))
        published = _normalize_date(clean_text(entry.findtext("pubDate")))
        summary = clean_text(entry.findtext("description"))
        items.append(
            FeedItem(
                item_id=stable_item_id(link=link, guid=guid, title=title),
                title=title,
                link=link,
                source=source.name,
                published=published,
                summary=summary,
                guid=guid,
                category=source.category,
            )
        )
    return items


def _parse_atom(root: ET.Element, source: FeedSource) -> list[FeedItem]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        title = clean_text(entry.findtext("atom:title", namespaces=ns)) or "Untitled"
        link = _atom_link(entry, ns)
        guid = clean_text(entry.findtext("atom:id", namespaces=ns))
        published = _normalize_date(
            clean_text(entry.findtext("atom:published", namespaces=ns))
            or clean_text(entry.findtext("atom:updated", namespaces=ns))
        )
        summary = clean_text(entry.findtext("atom:summary", namespaces=ns)) or clean_text(
            entry.findtext("atom:content", namespaces=ns)
        )
        items.append(
            FeedItem(
                item_id=stable_item_id(link=link, guid=guid, title=title),
                title=title,
                link=link,
                source=source.name,
                published=published,
                summary=summary,
                guid=guid,
                category=source.category,
            )
        )
    return items


def _atom_link(entry: ET.Element, ns: dict[str, str]) -> str:
    links = entry.findall("atom:link", ns)
    for link in links:
        if link.attrib.get("rel", "alternate") == "alternate" and link.attrib.get("href"):
            return link.attrib["href"]
    for link in links:
        if link.attrib.get("href"):
            return link.attrib["href"]
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return value
    return parsed.isoformat()


def _join_zh_list(values: list[str]) -> str:
    return "；".join(values) if values else "未启用 LLM 中文摘要，需人工判断。"


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip() or None


def classify_collection_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if isinstance(exc, httpx.HTTPStatusError):
        return "http_error"
    if isinstance(exc, httpx.TimeoutException) or "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if isinstance(exc, httpx.ConnectError) and (
        "name or service not known" in lowered
        or "nodename nor servname" in lowered
        or "getaddrinfo" in lowered
    ):
        return "dns_error"
    if "10013" in message or "permission" in lowered or "access" in lowered:
        return "socket_permission_denied"
    if isinstance(exc, ET.ParseError) or "unsupported feed root" in lowered or "not well-formed" in lowered:
        return "parse_error"
    if isinstance(exc, httpx.RequestError):
        return "network_error"
    return "unknown_error"


def diagnose_collection_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "10013" in message or "permission" in lowered or "access" in lowered:
        return "当前运行环境不允许 Python 建立该网络连接。可能原因包括 Windows 防火墙、杀毒软件、代理、沙箱网络限制或系统权限策略。"
    if "timeout" in lowered or "timed out" in lowered:
        return "网络请求超时，请检查网络连通性、代理配置或 RSS 源响应速度。"
    if "name or service not known" in lowered or "nodename nor servname" in lowered:
        return "DNS 解析失败，请检查网络、代理或 RSS URL 域名。"
    if "404" in message:
        return "RSS URL 返回 404，请检查 sources 配置中的 URL 是否仍然有效。"
    if "unsupported feed root" in lowered or "not well-formed" in lowered:
        return "响应内容不是有效 RSS/Atom XML，可能是网页、错误页或源格式变化。"
    return "采集失败，请检查网络、RSS URL、代理、防火墙或运行环境权限。"
