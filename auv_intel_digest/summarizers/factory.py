from __future__ import annotations

from auv_intel_digest.summarizers.fake import FakeSummarizer
from auv_intel_digest.summarizers.noop import NoopSummarizer
from auv_intel_digest.summarizers.openai_summarizer import OpenAISummarizer


def build_summarizer(name: str = "noop", *, llm_model: str | None = None):
    normalized = name.strip().lower()
    if normalized == "noop":
        return NoopSummarizer()
    if normalized == "fake":
        return FakeSummarizer()
    if normalized == "openai":
        return OpenAISummarizer(model=llm_model)
    return NoopSummarizer(f"未知 summarizer '{name}'，已回退为 noop。")
