from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SummaryResult:
    zh_title: str
    zh_summary: str
    key_points: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    importance: str = "medium"
    warning: str | None = None


class Summarizer(Protocol):
    name: str
    warnings: list[str]

    def summarize_item(self, item) -> SummaryResult:
        ...
