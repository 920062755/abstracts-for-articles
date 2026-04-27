from datetime import date
from pathlib import Path

from auv_intel_digest.dedupe.deduper import Deduper
from auv_intel_digest.dedupe.store import SeenStore
from auv_intel_digest.models import DuplicateStatus, IntelItem


def _sqlite_path(name: str) -> Path:
    path = Path("tests/.tmp") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    return path


def test_same_day_duplicates_are_marked_duplicate():
    items = [
        IntelItem(title="A Multi-AUV Planning Method", authors=[], source="a", url="https://x/1"),
        IntelItem(title="A Multi AUV Planning Method", authors=[], source="b", url="https://x/2"),
    ]

    result = Deduper(window_days=90).dedupe(items, date(2026, 4, 27))

    assert result[0].duplicate_status == DuplicateStatus.UNIQUE
    assert result[1].duplicate_status == DuplicateStatus.DUPLICATE


def test_recent_historical_duplicate_is_repeated():
    store = SeenStore(_sqlite_path("state_repeated.sqlite"))
    first = IntelItem(title="Pursuit Evasion for AUV Teams", authors=[], source="a", url="https://x/1")
    Deduper(store, window_days=90).dedupe([first], date(2026, 4, 1))

    repeated = IntelItem(
        title="Pursuit Evasion for AUV Teams",
        authors=[],
        source="b",
        url="https://x/1",
    )
    Deduper(store, window_days=90).dedupe([repeated], date(2026, 4, 27))

    assert repeated.duplicate_status == DuplicateStatus.REPEATED
    assert repeated.first_seen_date == "2026-04-01"


def test_recent_historical_duplicate_with_update_is_allowed_as_update():
    store = SeenStore(_sqlite_path("state_update.sqlite"))
    first = IntelItem(title="Multi-Agent Markov Game", authors=[], source="a", url="https://x/1")
    Deduper(store, window_days=90).dedupe([first], date(2026, 4, 1))

    updated = IntelItem(
        title="Multi-Agent Markov Game",
        authors=[],
        source="github",
        url="https://x/1",
        snippet="New version with GitHub code and dataset released.",
    )
    Deduper(store, window_days=90).dedupe([updated], date(2026, 4, 27))

    assert updated.duplicate_status == DuplicateStatus.UPDATE
