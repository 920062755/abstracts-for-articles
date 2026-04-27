import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

from auv_intel_digest.cli import app
from auv_intel_digest.scheduled_digest import (
    FeedItem,
    FeedSource,
    ScheduledDigestResult,
    load_state,
    mark_seen,
    parse_feed,
    render_scheduled_digest,
    run_scheduled_digest,
    write_state,
)
from auv_intel_digest.summarizers.fake import FakeSummarizer


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Robotics Feed</title>
    <item>
      <title>Multi-AUV field test</title>
      <link>https://example.test/rss/1</link>
      <guid>rss-guid-1</guid>
      <pubDate>Mon, 27 Apr 2026 08:00:00 +0800</pubDate>
      <description>Cooperative underwater robotics update.</description>
    </item>
  </channel>
</rss>
"""


ATOM_FIXTURE = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Robotics Feed</title>
  <entry>
    <id>atom-id-1</id>
    <title>Multi-agent planning release</title>
    <link href="https://example.test/atom/1" />
    <updated>2026-04-27T08:00:00+08:00</updated>
    <summary>New cooperative planning project update.</summary>
  </entry>
</feed>
"""


def test_rss_fixture_parses_basic_fields():
    items = parse_feed(RSS_FIXTURE, FeedSource("RSS Test", "https://feed.test", "robotics"))

    assert len(items) == 1
    assert items[0].title == "Multi-AUV field test"
    assert items[0].link == "https://example.test/rss/1"
    assert items[0].guid == "rss-guid-1"
    assert items[0].source == "RSS Test"
    assert items[0].category == "robotics"


def test_atom_fixture_parses_basic_fields():
    items = parse_feed(ATOM_FIXTURE, FeedSource("Atom Test", "https://feed.test", "planning"))

    assert len(items) == 1
    assert items[0].title == "Multi-agent planning release"
    assert items[0].link == "https://example.test/atom/1"
    assert items[0].guid == "atom-id-1"
    assert items[0].summary == "New cooperative planning project update."


def test_state_marks_seen_items_and_preserves_new_status():
    generated_at = "2026-04-27T08:00"
    item = FeedItem(
        item_id="same-id",
        title="Title",
        link="https://example.test",
        source="source",
    )
    state = {"seen": {}}

    mark_seen([item], state, generated_at)
    assert item.seen is False
    second = FeedItem(
        item_id="same-id",
        title="Title",
        link="https://example.test",
        source="source",
    )
    mark_seen([second], state, "2026-04-27T09:00")

    assert second.seen is True
    assert state["seen"]["same-id"]["first_seen"] == generated_at
    assert state["seen"]["same-id"]["last_seen"] == "2026-04-27T09:00"


def test_state_file_read_write_roundtrip():
    path = Path("tests/.tmp/scheduled_state.json")
    if path.exists():
        path.unlink()

    state = {"seen": {"id": {"title": "Title"}}}
    write_state(path, state)

    assert load_state(path) == state


def test_markdown_digest_contains_summary_items_and_errors():
    source = FeedSource("RSS Test", "https://feed.test")
    result = ScheduledDigestResult(
        generated_at="2026-04-27T08:00",
        sources_checked=2,
        successful=1,
        failed=1,
        new_items=1,
        output_limit=30,
        output_path=Path("digests/latest.md"),
        items=[
            FeedItem(
                item_id="id",
                title="Multi-AUV field test",
                link="https://example.test/rss/1",
                source="RSS Test",
                published="2026-04-27T08:00:00+08:00",
                summary="Summary",
                category="robotics",
            )
        ],
        source_results=[
            type("Result", (), {"source": source, "status": "ok", "items": [], "error": None})(),
            type(
                "Result",
                (),
                {"source": FeedSource("Broken", "https://broken.test"), "status": "error", "items": [], "error": "boom"},
            )(),
        ],
    )

    markdown = render_scheduled_digest(result)

    assert "# AUV Intel Digest" in markdown
    assert "- Sources checked: 2" in markdown
    assert "### 1. Multi-AUV field test" in markdown
    assert "- Broken: boom" in markdown


def test_chinese_markdown_digest_uses_summary_fields():
    source = FeedSource("RSS Test", "https://feed.test")
    item = FeedItem(
        item_id="id",
        title="Multi-AUV field test",
        link="https://example.test/rss/1",
        source="RSS Test",
        published="2026-04-27T08:00:00+08:00",
        summary="Summary",
        category="robotics",
    )
    result = ScheduledDigestResult(
        generated_at="2026-04-27T08:00",
        sources_checked=1,
        successful=1,
        failed=0,
        new_items=1,
        output_limit=30,
        output_path=Path("digests/latest.zh.md"),
        items=[item],
        source_results=[type("Result", (), {"source": source, "status": "ok", "items": [], "error": None})()],
        language="zh",
        summarizer_name="fake",
        summaries={item.item_id: FakeSummarizer().summarize_item(item)},
    )

    markdown = render_scheduled_digest(result)

    assert "# AUV 情报摘要" in markdown
    assert "## 运行摘要" in markdown
    assert "## 重点情报" in markdown
    assert "- 原始标题：Multi-AUV field test" in markdown
    assert "- 中文摘要：这是用于测试的中文摘要：Summary" in markdown
    assert "## 采集错误" in markdown


def test_run_scheduled_digest_uses_mock_network_and_filters_seen_items():
    sources_path = Path("tests/.tmp/sources.json")
    output_path = Path("tests/.tmp/latest.md")
    state_path = Path("tests/.tmp/run_state.json")
    for path in (sources_path, output_path, state_path):
        if path.exists():
            path.unlink()
    sources_path.write_text(
        json.dumps({"sources": [{"name": "RSS Test", "url": "https://feed.test/rss"}]}),
        encoding="utf-8",
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=RSS_FIXTURE))
    )

    first = run_scheduled_digest(
        sources_path=sources_path,
        output_path=output_path,
        limit=10,
        state_path=state_path,
        http_client=client,
    )
    second = run_scheduled_digest(
        sources_path=sources_path,
        output_path=output_path,
        limit=10,
        state_path=state_path,
        http_client=client,
    )

    assert first.new_items == 1
    assert len(first.items) == 1
    assert second.new_items == 0
    assert len(second.items) == 0
    assert output_path.exists()


def test_run_scheduled_digest_zh_with_fake_summarizer():
    sources_path = Path("tests/.tmp/sources_zh.json")
    output_path = Path("tests/.tmp/latest.zh.md")
    state_path = Path("tests/.tmp/run_state_zh.json")
    for path in (sources_path, output_path, state_path):
        if path.exists():
            path.unlink()
    sources_path.write_text(
        json.dumps({"sources": [{"name": "RSS Test", "url": "https://feed.test/rss"}]}),
        encoding="utf-8",
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=RSS_FIXTURE))
    )

    result = run_scheduled_digest(
        sources_path=sources_path,
        output_path=output_path,
        limit=10,
        state_path=state_path,
        language="zh",
        summarizer_name="fake",
        http_client=client,
    )

    markdown = output_path.read_text(encoding="utf-8")
    assert result.language == "zh"
    assert result.summarizer_name == "fake"
    assert "中文整理：Multi-AUV field test" in markdown


def test_scheduled_digest_cli_smoke(monkeypatch):
    def fake_run_scheduled_digest(**kwargs):
        return ScheduledDigestResult(
            generated_at="2026-04-27T08:00",
            sources_checked=1,
            successful=1,
            failed=0,
            new_items=1,
            output_limit=kwargs["limit"],
            output_path=kwargs["output_path"],
            items=[],
            source_results=[],
        )

    monkeypatch.setattr("auv_intel_digest.cli.run_scheduled_digest", fake_run_scheduled_digest)
    result = CliRunner().invoke(
        app,
        [
            "scheduled-digest",
            "--sources",
            "examples/sources.example.json",
            "--output",
            "tests/.tmp/cli.md",
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "Sources checked: 1" in result.output
    assert "Output: tests\\.tmp\\cli.md" in result.output or "Output: tests/.tmp/cli.md" in result.output


def test_collect_cli_alias_smoke(monkeypatch):
    def fake_run_scheduled_digest(**kwargs):
        return ScheduledDigestResult(
            generated_at="2026-04-27T08:00",
            sources_checked=1,
            successful=1,
            failed=0,
            new_items=1,
            output_limit=kwargs["limit"],
            output_path=kwargs["output_path"],
            items=[],
            source_results=[],
            language=kwargs["language"],
            summarizer_name=kwargs["summarizer_name"],
        )

    monkeypatch.setattr("auv_intel_digest.cli.run_scheduled_digest", fake_run_scheduled_digest)
    result = CliRunner().invoke(
        app,
        [
            "collect",
            "--sources",
            "examples/sources.example.json",
            "--output",
            "tests/.tmp/collect.md",
            "--limit",
            "5",
            "--state",
            "tests/.tmp/collect-state.json",
            "--include-seen",
            "--language",
            "zh",
            "--summarizer",
            "noop",
        ],
    )

    assert result.exit_code == 0
    assert "Sources checked: 1" in result.output
    assert "Language: zh" in result.output
