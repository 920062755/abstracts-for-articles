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
