import httpx

from auv_intel_digest.scheduled_digest import FeedItem
from auv_intel_digest.summarizers.fake import FakeSummarizer
from auv_intel_digest.summarizers.noop import NoopSummarizer
from auv_intel_digest.summarizers.openai_summarizer import OpenAISummarizer


def _item():
    return FeedItem(
        item_id="id",
        title="Multi-AUV cooperative planning",
        link="https://example.test/item",
        source="RSS Test",
        summary="A cooperative planning update for underwater robot teams.",
    )


def test_noop_summarizer_keeps_original_content_and_marks_no_llm():
    result = NoopSummarizer().summarize_item(_item())

    assert result.zh_title == "Multi-AUV cooperative planning"
    assert "未启用 LLM 中文摘要" in result.zh_summary
    assert "underwater robot teams" in result.zh_summary


def test_fake_summarizer_returns_deterministic_chinese_summary():
    result = FakeSummarizer().summarize_item(_item())

    assert result.zh_title.startswith("中文整理：")
    assert result.key_points == ["测试关键信息"]
    assert result.importance == "high"


def test_openai_summarizer_without_api_key_falls_back_to_noop(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    summarizer = OpenAISummarizer(api_key="")
    result = summarizer.summarize_item(_item())

    assert summarizer.warnings
    assert "OPENAI_API_KEY 未配置" in summarizer.warnings[0]
    assert "未启用 LLM 中文摘要" in result.zh_summary


def test_openai_summarizer_uses_mock_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"zh_title":"中文标题","zh_summary":"中文摘要",'
                                    '"key_points":["要点"],"risks":["风险"],'
                                    '"opportunities":["机会"],"follow_ups":["跟进"],'
                                    '"importance":"high"}'
                                )
                            }
                        }
                    ]
                },
            )
        )
    )

    result = OpenAISummarizer(model="test-model", http_client=client).summarize_item(_item())

    assert result.zh_title == "中文标题"
    assert result.key_points == ["要点"]
