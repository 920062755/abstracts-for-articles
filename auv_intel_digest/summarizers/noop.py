from __future__ import annotations

from auv_intel_digest.summarizers.base import SummaryResult


class NoopSummarizer:
    name = "noop"

    def __init__(self, warning: str | None = None) -> None:
        self.warnings = [warning] if warning else []

    def summarize_item(self, item) -> SummaryResult:
        original_summary = item.summary or "原始条目未提供 summary/description。"
        prefix = "未启用 LLM 中文摘要，以下为原始摘要。"
        return SummaryResult(
            zh_title=item.title,
            zh_summary=f"{prefix}\n\n{original_summary}",
            key_points=["保留原始标题、链接和摘要，供人工快速判断。"],
            risks=["未进行中文深度摘要，可能遗漏方法、实验和结论细节。"],
            opportunities=["可根据标题和原始摘要判断是否加入当日精读列表。"],
            follow_ups=["打开原文链接，检查是否与 AUV/UUV 或多智能体研究方向相关。"],
            importance="medium",
            warning=self.warnings[0] if self.warnings else None,
        )
