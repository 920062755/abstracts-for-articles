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


def test_openai_compatible_uses_fallback_model_after_timeout():
    requested_models = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requested_models.append(payload["model"])
        if payload["model"] == "Qwen/Qwen2.5-7B-Instruct":
            raise httpx.ReadTimeout("slow model", request=request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "zh_title": "备用模型摘要",
                                    "zh_summary": "备用模型已成功生成摘要",
                                    "key_points": ["fallback"],
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
        fallback_models=[
            "Pro/Qwen/Qwen2.5-7B-Instruct",
            "deepseek-ai/DeepSeek-V3",
        ],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = summarizer.summarize_item(_item())

    assert requested_models == [
        "Qwen/Qwen2.5-7B-Instruct",
        "Pro/Qwen/Qwen2.5-7B-Instruct",
    ]
    assert result.zh_title == "备用模型摘要"
    assert any("备用模型 Pro/Qwen/Qwen2.5-7B-Instruct" in warning for warning in summarizer.warnings)


def test_openai_compatible_reports_response_preview_after_all_models_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<html>gateway timeout</html>",
            headers={"content-type": "text/html"},
        )

    summarizer = OpenAICompatibleSummarizer(
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
        fallback_models=["deepseek-ai/DeepSeek-V3"],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = summarizer.summarize_item(_item())

    assert result.warning is not None
    assert "response_JSONDecodeError" in result.warning
    assert "gateway timeout" in result.warning
    assert "test-key" not in result.warning


def test_openai_compatible_respects_max_items_limit():
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
        model="Qwen/Qwen2.5-7B-Instruct",
        max_items=1,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    first = summarizer.summarize_item(_item())
    second = summarizer.summarize_item(_item())

    assert first.zh_title == "中文标题"
    assert second.warning is not None
    assert "LLM 摘要条目数已达到上限 1" in second.warning
    assert len(requests) == 1


def test_factory_accepts_siliconflow_alias(monkeypatch):
    monkeypatch.delenv("AUV_INTEL_LLM_API_KEY", raising=False)
    summarizer = build_summarizer("siliconflow")

    assert isinstance(summarizer, OpenAICompatibleSummarizer)
