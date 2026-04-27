from __future__ import annotations

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from auv_intel_digest.models import IntelItem, SourceStatus, Topic
from auv_intel_digest.settings import Settings


@dataclass(frozen=True)
class CollectionWindow:
    start: date
    end: date

    @classmethod
    def from_report_date(cls, report_date: date, days_back: int) -> "CollectionWindow":
        return cls(start=report_date - timedelta(days=days_back), end=report_date)


@dataclass
class CollectionResult:
    source: str
    items: list[IntelItem]
    status: SourceStatus


class SourceClient:
    name: str

    def __init__(
        self,
        config: dict[str, Any],
        settings: Settings,
        global_config: dict[str, Any],
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.settings = settings
        self.global_config = global_config
        self.http_client = http_client

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        raise NotImplementedError

    @property
    def max_results(self) -> int:
        return int(self.config.get("max_results") or self.global_config.get("max_items_per_source", 50))

    @property
    def timeout(self) -> float:
        return float(self.global_config.get("request_timeout_seconds", 20))

    @property
    def headers(self) -> dict[str, str]:
        configured = str(self.global_config.get("user_agent", "auv_intel_digest/0.2"))
        user_agent = configured.replace("${CONTACT_EMAIL}", self.settings.contact_email)
        return {"User-Agent": user_agent}

    def client(self) -> httpx.Client:
        if self.http_client:
            return self.http_client
        return httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True)

    @contextmanager
    def managed_client(self):
        if self.http_client:
            yield self.http_client
            return
        with self.client() as client:
            yield client


def topic_query(topic: Topic, max_terms: int = 8) -> str:
    terms: list[str] = []
    for lang in ("en", "zh"):
        lang_config = topic.keywords.get(lang, {})
        terms.extend(lang_config.get("positive", []))
        terms.extend(lang_config.get("required_any", []))
    cleaned = [term.strip() for term in terms if term and term.strip()]
    return " OR ".join(list(dict.fromkeys(cleaned))[:max_terms])


def all_topic_queries(topics: list[Topic]) -> list[tuple[Topic, str]]:
    return [(topic, query) for topic in topics if topic.enabled and (query := topic_query(topic))]


def env_value(name: str | None) -> str:
    if not name:
        return ""
    return os.getenv(name, "")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip() or None


def date_from_parts(parts: list[list[int]] | None) -> str | None:
    if not parts or not parts[0]:
        return None
    values = parts[0]
    year = values[0]
    month = values[1] if len(values) > 1 else 1
    day = values[2] if len(values) > 2 else 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
