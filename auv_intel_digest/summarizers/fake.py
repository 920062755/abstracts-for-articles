from __future__ import annotations

from auv_intel_digest.summarizers.base import SummaryResult


class FakeSummarizer:
    name = "fake"

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def summarize_item(self, item) -> SummaryResult:
        return SummaryResult(
            zh_title=f"中文整理：{item.title}",
            zh_summary=f"这是用于测试的中文摘要：{item.summary or item.title}",
            key_points=["测试关键信息"],
            risks=["测试风险"],
            opportunities=["测试机会"],
            follow_ups=["测试建议跟进"],
            importance="high",
        )
