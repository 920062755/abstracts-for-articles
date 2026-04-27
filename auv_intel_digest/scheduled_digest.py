from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from auv_intel_digest.summarizers import SummaryResult, build_summarizer
from auv_intel_digest.sources.base import clean_text


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


def load_feed_sources(path: str | Path) -> list[FeedSource]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    sources_data = data.get("sources", data if isinstance(data, list) else [])
    sources = []
    for entry in sources_data:
        sources.append(
            FeedSource(
                name=entry["name"],
                url=entry["url"],
                category=entry.get("category"),
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return sources


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
    user_agent: str = "auv_intel_digest/0.3",
    http_client: httpx.Client | None = None,
) -> list[FeedSourceResult]:
    enabled_sources = [source for source in sources if source.enabled]
    results: list[FeedSourceResult] = []
    client = http_client or httpx.Client(timeout=timeout, headers={"User-Agent": user_agent})
    close_client = http_client is None
    try:
        for source in enabled_sources:
            try:
                response = client.get(source.url)
                response.raise_for_status()
                items = parse_feed(response.text, source)
                results.append(FeedSourceResult(source=source, status="ok", items=items))
            except Exception as exc:
                results.append(
                    FeedSourceResult(source=source, status="error", items=[], error=str(exc))
                )
    finally:
        if close_client:
            client.close()
    return results


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
        f"- Output limit: {result.output_limit}",
        "",
        "## Highlights",
        "",
    ]
    if not result.items:
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

    errors = [source for source in result.source_results if source.status != "ok"]
    lines.extend(["## Source Errors", ""])
    if not errors:
        lines.extend(["None.", ""])
    for error in errors:
        lines.append(f"- {error.source.name}: {error.error or 'Unknown error'}")
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
        lines.extend(["今日暂无新条目。", ""])
    for idx, item in enumerate(result.items, start=1):
        summary = result.summaries.get(item.item_id)
        title = summary.zh_title if summary and summary.zh_title else item.title
        lines.extend(
            [
                f"### {idx}. {title}",
                "",
                f"- 来源：{item.source}",
                f"- 发布时间：{item.published or '未知'}",
                f"- 链接：{item.link or 'N/A'}",
                f"- 原始标题：{item.title}",
                f"- 中文摘要：{summary.zh_summary if summary else '未启用 LLM 中文摘要，以下为原始摘要。 ' + (item.summary or '原始条目未提供摘要。')}",
                f"- 关键信息：{_join_zh_list(summary.key_points if summary else [])}",
                f"- 风险：{_join_zh_list(summary.risks if summary else [])}",
                f"- 机会：{_join_zh_list(summary.opportunities if summary else [])}",
                f"- 建议跟进：{_join_zh_list(summary.follow_ups if summary else [])}",
                "",
            ]
        )

    errors = [source for source in result.source_results if source.status != "ok"]
    lines.extend(["## 采集错误", ""])
    if not errors:
        lines.extend(["无。", ""])
    for error in errors:
        lines.append(f"- {error.source.name}: {error.error or '未知错误'}")
    return "\n".join(lines).rstrip() + "\n"


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
) -> ScheduledDigestResult:
    generated_at = datetime.now().isoformat(timespec="minutes")
    sources = load_feed_sources(sources_path)
    enabled_sources = [source for source in sources if source.enabled]
    source_results = collect_feed_sources(enabled_sources, http_client=http_client)
    all_items = [item for result in source_results for item in result.items]
    state = load_state(state_path)
    mark_seen(all_items, state, generated_at)
    write_state(state_path, state)

    selected = all_items if include_seen else [item for item in all_items if not item.seen]
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
        sources_checked=len(enabled_sources),
        successful=sum(1 for result in source_results if result.status == "ok"),
        failed=sum(1 for result in source_results if result.status != "ok"),
        new_items=sum(1 for item in all_items if not item.seen),
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
