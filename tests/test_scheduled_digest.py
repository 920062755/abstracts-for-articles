import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

from auv_intel_digest.cli import app
from auv_intel_digest.scheduled_digest import (
    FeedItem,
    FeedSource,
    FeedSourceResult,
    ScheduledDigestResult,
    all_sources_failed,
    check_feed_sources,
    classify_collection_error,
    diagnose_collection_error,
    load_state,
    mark_seen,
    parse_feed,
    render_scheduled_digest,
    run_scheduled_digest,
    run_status_zh,
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


def test_check_feed_sources_reports_success_failure_and_disabled():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://feed.test/rss":
            return httpx.Response(
                200,
                text=RSS_FIXTURE,
                headers={"content-type": "application/rss+xml; charset=utf-8"},
            )
        return httpx.Response(404, text="missing", headers={"content-type": "text/plain"})

    diagnostics = check_feed_sources(
        [
            FeedSource("Good", "https://feed.test/rss", "robotics"),
            FeedSource("Missing", "https://feed.test/missing", "robotics"),
            FeedSource("Disabled", "https://feed.test/disabled", enabled=False),
        ],
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert diagnostics[0].http_status == 200
    assert diagnostics[0].content_type == "application/rss+xml; charset=utf-8"
    assert diagnostics[0].byte_count > 0
    assert diagnostics[0].parseable is True
    assert diagnostics[0].item_count == 1
    assert diagnostics[1].http_status == 404
    assert diagnostics[1].error_type == "http_error"
    assert diagnostics[2].enabled is False
    assert diagnostics[2].error_type == "disabled"


def test_state_marks_seen_items_and_preserves_new_status():
    generated_at = "2026-04-27T08:00"
    item = FeedItem(item_id="same-id", title="Title", link="https://example.test", source="source")
    state = {"seen": {}}

    mark_seen([item], state, generated_at)
    second = FeedItem(item_id="same-id", title="Title", link="https://example.test", source="source")
    mark_seen([second], state, "2026-04-27T09:00")

    assert item.seen is False
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


def test_markdown_digest_contains_summary_items_errors_and_diagnostics():
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
            FeedSourceResult(source=FeedSource("RSS Test", "https://feed.test"), status="ok"),
            FeedSourceResult(
                source=FeedSource("Broken", "https://broken.test"),
                status="error",
                error="boom",
                error_type="unknown_error",
                diagnostic="Check source config.",
            ),
        ],
    )

    markdown = render_scheduled_digest(result)

    assert "# AUV Intel Digest" in markdown
    assert "- Sources checked: 2" in markdown
    assert "### 1. Multi-AUV field test" in markdown
    assert "- Broken:" in markdown
    assert "Error type: unknown_error" in markdown
    assert "Raw error: boom" in markdown
    assert "Explanation: Check source config." in markdown


def test_chinese_markdown_digest_uses_summary_fields():
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
        source_results=[FeedSourceResult(source=FeedSource("RSS Test", "https://feed.test"), status="ok")],
        language="zh",
        summarizer_name="fake",
        summaries={item.item_id: FakeSummarizer().summarize_item(item)},
    )

    markdown = render_scheduled_digest(result)

    assert "Multi-AUV field test" in markdown
    assert "Summary" in markdown
    assert "fake" in markdown


def test_chinese_digest_all_sources_failed_uses_failure_guard_semantics():
    result = ScheduledDigestResult(
        generated_at="2026-04-27T08:00",
        sources_checked=2,
        successful=0,
        failed=2,
        new_items=0,
        output_limit=30,
        output_path=Path("digests/latest.zh.md"),
        items=[],
        source_results=[
            FeedSourceResult(
                source=FeedSource("RSS A", "https://a.test"),
                status="error",
                error="[WinError 10013] access denied",
                error_type="socket_permission_denied",
                diagnostic=diagnose_collection_error(PermissionError("[WinError 10013] access denied")),
            ),
            FeedSourceResult(
                source=FeedSource("RSS B", "https://b.test"),
                status="error",
                error="timeout",
                error_type="timeout",
                diagnostic=diagnose_collection_error(TimeoutError("timeout")),
            ),
        ],
        language="zh",
        summarizer_name="noop",
    )

    markdown = render_scheduled_digest(result)

    assert all_sources_failed(result) is True
    assert run_status_zh(result) == "全部失败"
    assert "socket_permission_denied" in markdown
    assert "[WinError 10013] access denied" in markdown
    assert "timeout" in markdown


def test_collection_error_classifies_winerror_10013_as_socket_permission_denied():
    exc = PermissionError("[WinError 10013] access denied")

    assert classify_collection_error(exc) == "socket_permission_denied"


def test_chinese_digest_reports_partial_success_status():
    result = ScheduledDigestResult(
        generated_at="2026-04-27T08:00",
        sources_checked=2,
        successful=1,
        failed=1,
        new_items=1,
        output_limit=30,
        output_path=Path("digests/latest.zh.md"),
        items=[],
        source_results=[
            FeedSourceResult(source=FeedSource("Good", "https://good.test"), status="ok"),
            FeedSourceResult(source=FeedSource("Broken", "https://broken.test"), status="error"),
        ],
        language="zh",
        summarizer_name="noop",
    )

    assert run_status_zh(result) == "部分成功"


def test_chinese_digest_reports_no_new_status_when_all_sources_successful_without_new_items():
    result = ScheduledDigestResult(
        generated_at="2026-04-27T08:00",
        sources_checked=1,
        successful=1,
        failed=0,
        new_items=0,
        output_limit=30,
        output_path=Path("digests/latest.zh.md"),
        items=[],
        source_results=[FeedSourceResult(source=FeedSource("Good", "https://good.test"), status="ok")],
        language="zh",
        summarizer_name="noop",
    )

    assert run_status_zh(result) == "无新增"


def test_all_sources_failed_without_strict_flag_does_not_update_state():
    sources_path = Path("tests/.tmp/all_failed_compat_sources.json")
    output_path = Path("tests/.tmp/all_failed_compat.md")
    state_path = Path("tests/.tmp/all_failed_compat_state.json")
    for path in (sources_path, output_path, state_path):
        if path.exists():
            path.unlink()
    sources_path.write_text(
        json.dumps({"sources": [{"name": "Broken", "url": "https://broken.test/rss"}]}),
        encoding="utf-8",
    )
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, text="broken")))

    result = run_scheduled_digest(
        sources_path=sources_path,
        output_path=output_path,
        limit=10,
        state_path=state_path,
        language="zh",
        http_client=client,
    )

    assert result.successful == 0
    assert result.failed == 1
    assert output_path.exists()
    assert not state_path.exists()


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
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=RSS_FIXTURE)))

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
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=RSS_FIXTURE)))

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
    assert "Multi-AUV field test" in markdown


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


def test_collect_cli_fail_on_all_source_errors_exits_two(monkeypatch):
    def fake_run_scheduled_digest(**kwargs):
        return ScheduledDigestResult(
            generated_at="2026-04-27T08:00",
            sources_checked=2,
            successful=0,
            failed=2,
            new_items=0,
            output_limit=kwargs["limit"],
            output_path=kwargs["output_path"],
            items=[],
            source_results=[FeedSourceResult(source=FeedSource("Broken", "https://broken.test"), status="error")],
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
            "--fail-on-all-source-errors",
        ],
    )

    assert result.exit_code == 2
    assert "All sources failed: true" in result.output


def test_check_sources_cli_smoke(monkeypatch):
    monkeypatch.setattr(
        "auv_intel_digest.cli.load_feed_sources",
        lambda path: [FeedSource("Good", "https://feed.test/rss", "robotics")],
    )
    monkeypatch.setattr(
        "auv_intel_digest.cli.check_feed_sources",
        lambda sources, timeout, user_agent=None: [
            type(
                "Diagnostic",
                (),
                {
                    "name": "Good",
                    "url": "https://feed.test/rss",
                    "enabled": True,
                    "category": "robotics",
                    "http_status": 200,
                    "content_type": "application/rss+xml",
                    "byte_count": 123,
                    "parseable": True,
                    "item_count": 1,
                    "error_type": None,
                    "error_message": None,
                    "diagnostic": None,
                },
            )()
        ],
    )

    result = CliRunner().invoke(app, ["check-sources", "--sources", "examples/sources.example.json", "--timeout", "3"])

    assert result.exit_code == 0
    assert "Name: Good" in result.output
    assert "HTTP status: 200" in result.output
    assert "Parseable RSS/Atom: true" in result.output
    assert "Checked: 1" in result.output
    assert "Successful: 1" in result.output
    assert "Failed: 0" in result.output
