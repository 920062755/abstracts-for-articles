from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from auv_intel_digest.classify.keyword_classifier import KeywordClassifier
from auv_intel_digest.config_loader import load_sources_config, load_topics
from auv_intel_digest.dedupe.deduper import Deduper
from auv_intel_digest.dedupe.store import SeenStore
from auv_intel_digest.models import DailyDigest
from auv_intel_digest.notifiers.composite import CompositeNotifier
from auv_intel_digest.notifiers.file_only import FileOnlyNotifier
from auv_intel_digest.notifiers.qq_onebot import QQOneBotNotifier
from auv_intel_digest.reports.json_writer import write_json
from auv_intel_digest.reports.markdown import daily_report_paths, render_html, render_markdown, write_markdown
from auv_intel_digest.settings import Settings
from auv_intel_digest.sources.factory import build_collectors, collect_from_sources

logger = logging.getLogger(__name__)


def resolve_timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Shanghai":
            return timezone(timedelta(hours=8), name="Asia/Shanghai")
        raise


def build_notifier(settings: Settings, digest: DailyDigest) -> CompositeNotifier:
    notifiers = [FileOnlyNotifier()]
    modes = {mode.strip() for mode in settings.notifier_mode.split(",") if mode.strip()}
    if "qq" in modes or "qq_onebot" in modes:
        notifiers.append(
            QQOneBotNotifier(
                endpoint=settings.qq_onebot_endpoint,
                access_token=settings.qq_onebot_access_token,
                target_type=settings.qq_target_type,
                target_id=settings.qq_target_id,
                push_mode=settings.qq_push_mode,
                push_max_chars=settings.qq_push_max_chars,
                digest=digest,
                max_items_per_topic=settings.max_items_per_topic,
            )
        )
    return CompositeNotifier(notifiers, strict=settings.strict_notify)


def run_digest(settings: Settings, report_date: date | None = None) -> dict[str, str]:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    tz = resolve_timezone(settings.timezone)
    now = datetime.now(tz)
    run_date = report_date or now.date()

    topics = load_topics()
    sources_config = load_sources_config()
    days_back = int(sources_config.get("global", {}).get("days_back", 1))
    collectors = build_collectors(sources_config, settings)
    items, source_status = collect_from_sources(
        collectors=collectors,
        topics=topics,
        report_date=run_date,
        days_back=days_back,
    )

    classifier = KeywordClassifier(topics)
    items = [classifier.classify(item) for item in items]

    deduper = Deduper(SeenStore(settings.state_db_path), window_days=settings.dedup_window_days)
    deduper.dedupe(items, run_date)

    digest = DailyDigest(
        report_date=run_date,
        generated_at=now.isoformat(timespec="seconds"),
        timezone=settings.timezone,
        items=items,
        topics=topics,
        source_status=source_status,
    )

    paths = daily_report_paths(settings.output_dir, run_date, settings.save_html)
    markdown = render_markdown(digest, settings.max_items_per_topic)
    write_markdown(paths["markdown"], markdown)
    write_json(paths["json"], digest)

    html_path = paths.get("html")
    if html_path:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(markdown), encoding="utf-8")

    notifier = build_notifier(settings, digest)
    notifier.send(
        title=f"AUV/UUV 科研资讯日报 - {run_date.isoformat()}",
        markdown=markdown,
        markdown_path=paths["markdown"],
        json_path=paths["json"],
        html_path=html_path,
    )

    return {key: str(path) for key, path in paths.items()}
