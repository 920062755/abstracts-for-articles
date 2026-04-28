import json

import httpx

from auv_intel_digest.scheduled_digest import FeedItem
from auv_intel_digest.summarizers.factory import build_summarizer
from auv_intel_digest.summarizers.openai_compatible import OpenAICompatibleSummarizer


def _item():
    return FeedItem(
        item_id="id",
        title="Multi-AUV cooperative planning",
        link="https://example.test/item",
        source="RSS Test",
        summary="A cooperative planning update for underwater robot teams.",
    )


def test_openai_compatible_without_api_key_falls_back_to_noop(monkeypatch):
    monkeypatch.delenv("AUV_INTEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    summarizer = OpenAICompatibleSummarizer(api_key="")
    result = summarizer.summarize_item(_item())

    assert summarizer.warnings
    assert "Multi-AUV cooperative planning" == result.zh_title


def test_openai_compatible_uses_mock_siliconflow_endpoint(monkeypatch):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "zh_title": "中文标题",
                                    "zh_summary": "中文摘要",
                                    "key_points": ["要点"],
                                    "risks": ["风险"],
                                    "opportunities": ["机会"],
                                    "follow_ups": ["跟进"],
                                    "importance": "high",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    summarizer = OpenAICompatibleSummarizer(
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = summarizer.summarize_item(_item())

    assert result.zh_title == "中文标题"
    assert result.key_points == ["要点"]
    assert str(requests[0].url) == "https://api.siliconflow.cn/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-key"


def test_factory_accepts_siliconflow_alias(monkeypatch):
    monkeypatch.delenv("AUV_INTEL_LLM_API_KEY", raising=False)
    summarizer = build_summarizer("siliconflow")

    assert isinstance(summarizer, OpenAICompatibleSummarizer)
