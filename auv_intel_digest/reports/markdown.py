from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from auv_intel_digest.models import DailyDigest, DuplicateStatus, IntelItem, Topic


def selectable_items(items: list[IntelItem]) -> list[IntelItem]:
    return [
        item
        for item in items
        if item.topic
        and item.duplicate_status in {DuplicateStatus.UNIQUE, DuplicateStatus.UPDATE}
        and item.score >= 0.35
    ]


def selected_by_topic(items: list[IntelItem], topics: list[Topic], limit: int) -> dict[str, list[IntelItem]]:
    grouped: dict[str, list[IntelItem]] = defaultdict(list)
    for item in selectable_items(items):
        grouped[item.topic or ""].append(item)

    selected: dict[str, list[IntelItem]] = {}
    for topic in topics:
        topic_items = sorted(
            grouped.get(topic.key, []),
            key=lambda item: (item.score, item.published_date or ""),
            reverse=True,
        )
        selected[topic.key] = topic_items[:limit]
    return selected


def top_items(items: list[IntelItem], limit: int = 3) -> list[IntelItem]:
    return sorted(selectable_items(items), key=lambda item: item.score, reverse=True)[:limit]


def render_markdown(digest: DailyDigest, max_items_per_topic: int = 5) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("daily_report.md.j2")
    selected = selected_by_topic(digest.items, digest.topics, max_items_per_topic)
    return template.render(
        digest=digest,
        selected_by_topic=selected,
        top_items=top_items(digest.items, 3),
        max_items_per_topic=max_items_per_topic,
    )


def daily_report_paths(output_dir: Path, report_date: date, save_html: bool = False) -> dict[str, Path]:
    daily_dir = output_dir / "daily"
    paths = {
        "markdown": daily_dir / f"{report_date.isoformat()}.md",
        "json": daily_dir / f"{report_date.isoformat()}.json",
    }
    if save_html:
        paths["html"] = daily_dir / f"{report_date.isoformat()}.html"
    return paths


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_html(markdown: str) -> str:
    escaped = (
        markdown.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>\n")
    )
    return f"<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><body>{escaped}</body></html>"
