from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from auv_intel_digest.models import IntelItem, SourceStatus, Topic
from auv_intel_digest.settings import Settings
from auv_intel_digest.sources.arxiv import ArxivClient
from auv_intel_digest.sources.base import CollectionWindow, SourceClient
from auv_intel_digest.sources.crossref import CrossrefClient
from auv_intel_digest.sources.github import GitHubClient
from auv_intel_digest.sources.openalex import OpenAlexClient
from auv_intel_digest.sources.rss import RssAtomClient

logger = logging.getLogger(__name__)

CLIENTS: dict[str, type[SourceClient]] = {
    "arxiv": ArxivClient,
    "crossref": CrossrefClient,
    "openalex": OpenAlexClient,
    "github": GitHubClient,
    "rss": RssAtomClient,
}


def build_collectors(
    sources_config: dict[str, Any],
    settings: Settings,
    http_client: httpx.Client | None = None,
) -> list[SourceClient]:
    global_config = sources_config.get("global", {})
    collectors: list[SourceClient] = []
    for source_name, config in sources_config.get("sources", {}).items():
        if not config.get("enabled", False):
            continue
        source_type = config.get("type", source_name)
        client_cls = CLIENTS.get(source_type)
        if not client_cls:
            logger.info("Skipping unsupported source type %s", source_type)
            continue
        collectors.append(client_cls(config, settings, global_config, http_client=http_client))
    return collectors


def collect_from_sources(
    *,
    collectors: list[SourceClient],
    topics: list[Topic],
    report_date: date,
    days_back: int,
) -> tuple[list[IntelItem], list[SourceStatus]]:
    window = CollectionWindow.from_report_date(report_date, days_back)
    items: list[IntelItem] = []
    statuses: list[SourceStatus] = []
    for collector in collectors:
        try:
            source_items = collector.fetch(topics, window)
            items.extend(source_items)
            statuses.append(
                SourceStatus(source=collector.name, status="ok", items=len(source_items), error=None)
            )
        except Exception as exc:
            logger.warning("Source %s failed: %s", collector.name, exc)
            statuses.append(SourceStatus(source=collector.name, status="error", items=0, error=str(exc)))
    return items, statuses
