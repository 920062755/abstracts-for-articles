import json
from datetime import date
from pathlib import Path

from auv_intel_digest.models import IntelItem, SourceStatus
from auv_intel_digest.pipeline import run_digest
from auv_intel_digest.settings import Settings


def test_pipeline_connects_collection_classification_dedupe_and_report_writing(monkeypatch):
    output_dir = Path("tests/.tmp/pipeline_reports")
    state_db = Path("tests/.tmp/pipeline_state.sqlite")
    if state_db.exists():
        state_db.unlink()

    def fake_collect_from_sources(*, collectors, topics, report_date, days_back):
        return (
            [
                IntelItem(
                    title="Multi-agent cooperative planning for robot teams",
                    authors=["A"],
                    source="arxiv",
                    url="https://example.test/multi-agent-planning",
                    published_date="2026-04-27",
                    abstract="A multi-agent planning method for cooperative robot teams.",
                )
            ],
            [SourceStatus(source="arxiv", status="ok", items=1)],
        )

    monkeypatch.setattr("auv_intel_digest.pipeline.load_sources_config", lambda: {"global": {"days_back": 1}})
    monkeypatch.setattr("auv_intel_digest.pipeline.build_collectors", lambda config, settings: [object()])
    monkeypatch.setattr("auv_intel_digest.pipeline.collect_from_sources", fake_collect_from_sources)

    paths = run_digest(
        Settings(output_dir=output_dir, state_db_path=state_db, notifier_mode="file_only"),
        report_date=date(2026, 4, 27),
    )

    markdown_path = Path(paths["markdown"])
    json_path = Path(paths["json"])
    assert markdown_path.exists()
    assert json_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["items"][0]["topic"] == "multi_agent_planning"
    assert data["items"][0]["duplicate_status"] == "unique"
