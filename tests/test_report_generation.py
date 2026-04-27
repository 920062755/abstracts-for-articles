from datetime import date

from auv_intel_digest.models import DailyDigest, DuplicateStatus, IntelItem, Topic
from auv_intel_digest.reports.json_writer import digest_to_json_dict
from auv_intel_digest.reports.markdown import render_markdown, selected_by_topic


def _topics():
    return [
        Topic(
            key="multi_agent_planning",
            name_zh="多智能体协同规划",
            name_en="Multi-Agent Cooperative Planning",
            enabled=True,
            weight=1.0,
            keywords={},
            tags=[],
        ),
        Topic(
            key="multi_agent_game",
            name_zh="多智能体博弈",
            name_en="Multi-Agent Games",
            enabled=True,
            weight=1.0,
            keywords={},
            tags=[],
        ),
    ]


def _digest(items):
    return DailyDigest(
        report_date=date(2026, 4, 27),
        generated_at="2026-04-27T08:00:00+08:00",
        timezone="Asia/Shanghai",
        items=items,
        topics=_topics(),
        source_status=[],
    )


def test_markdown_limits_selected_items_per_topic_and_keeps_empty_topic():
    items = [
        IntelItem(
            title=f"Multi-agent planning paper {idx}",
            authors=[],
            source="arxiv",
            url=f"https://x/{idx}",
            topic="multi_agent_planning",
            score=1.0 - idx * 0.01,
            matched_keywords=["multi-agent planning"],
            duplicate_status=DuplicateStatus.UNIQUE,
        )
        for idx in range(7)
    ]
    digest = _digest(items)

    selected = selected_by_topic(digest.items, digest.topics, limit=5)
    markdown = render_markdown(digest, max_items_per_topic=5)

    assert len(selected["multi_agent_planning"]) == 5
    assert "今日暂无高相关更新" in markdown
    assert "多智能体博弈" in markdown


def test_json_keeps_complete_candidate_fields_and_repeated_items():
    item = IntelItem(
        title="Repeated Markov game item",
        authors=["A"],
        source="openalex",
        url="https://x/repeated",
        published_date="2026-04-27",
        abstract="abstract",
        topic="multi_agent_game",
        matched_keywords=["Markov game"],
        score=0.9,
        reason="推荐理由",
        tags=["game theory"],
        duplicate_status=DuplicateStatus.REPEATED,
        first_seen_date="2026-04-01",
        last_seen_date="2026-04-27",
    )

    data = digest_to_json_dict(_digest([item]))

    assert data["items"][0]["title"] == item.title
    assert data["items"][0]["duplicate_status"] == "repeated"
    assert data["items"][0]["first_seen_date"] == "2026-04-01"
    assert data["items"][0]["last_seen_date"] == "2026-04-27"
    assert "matched_keywords" in data["items"][0]
