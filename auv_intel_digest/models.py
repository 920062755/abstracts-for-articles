from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class DuplicateStatus(StrEnum):
    UNIQUE = "unique"
    DUPLICATE = "duplicate"
    REPEATED = "repeated"
    UPDATE = "update"


@dataclass
class Topic:
    key: str
    name_zh: str
    name_en: str
    enabled: bool
    weight: float
    keywords: dict[str, dict[str, list[str]]]
    tags: list[str] = field(default_factory=list)


@dataclass
class IntelItem:
    title: str
    authors: list[str]
    source: str
    url: str
    published_date: str | None = None
    abstract: str | None = None
    snippet: str | None = None
    topic: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    score: float = 0.0
    reason: str = ""
    tags: list[str] = field(default_factory=list)
    duplicate_status: DuplicateStatus = DuplicateStatus.UNIQUE
    first_seen_date: str | None = None
    last_seen_date: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duplicate_status"] = str(self.duplicate_status)
        return data


@dataclass
class SourceStatus:
    source: str
    status: str
    items: int
    error: str | None = None


@dataclass
class DailyDigest:
    report_date: date
    generated_at: str
    timezone: str
    items: list[IntelItem]
    topics: list[Topic]
    source_status: list[SourceStatus] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return len(self.items)
