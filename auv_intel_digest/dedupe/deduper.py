from __future__ import annotations

from datetime import date, datetime, timedelta

from auv_intel_digest.dedupe.normalizer import normalize_title, similarity
from auv_intel_digest.dedupe.store import SeenStore
from auv_intel_digest.models import DuplicateStatus, IntelItem


class Deduper:
    def __init__(self, store: SeenStore | None = None, window_days: int = 90) -> None:
        self.store = store
        self.window_days = window_days

    def dedupe(self, items: list[IntelItem], run_date: date) -> list[IntelItem]:
        seen_today: dict[str, IntelItem] = {}
        seen_titles: dict[str, str] = {}
        rows_to_store: list[tuple[str, IntelItem]] = []

        for item in items:
            key = self._identity_key(item)
            item.first_seen_date = item.first_seen_date or run_date.isoformat()
            item.last_seen_date = run_date.isoformat()

            today_duplicate = key in seen_today or self._similar_title_seen(item.title, seen_titles)
            historical = self.store.get(key) if self.store else None

            if today_duplicate:
                item.duplicate_status = DuplicateStatus.DUPLICATE
            elif historical and self._inside_window(historical["last_seen_date"], run_date):
                item.first_seen_date = historical["first_seen_date"]
                item.duplicate_status = self._status_for_repeated_item(item)
            else:
                item.duplicate_status = DuplicateStatus.UNIQUE

            seen_today[key] = item
            seen_titles[normalize_title(item.title)] = key
            rows_to_store.append((key, item))

        if self.store:
            self.store.upsert_many(rows_to_store)
        return items

    def _identity_key(self, item: IntelItem) -> str:
        if item.doi:
            return f"doi:{item.doi.casefold().strip()}"
        if item.arxiv_id:
            return f"arxiv:{item.arxiv_id.casefold().strip()}"
        if item.url:
            return f"url:{item.url.casefold().strip().rstrip('/')}"
        return f"title:{normalize_title(item.title)}"

    def _similar_title_seen(self, title: str, seen_titles: dict[str, str]) -> bool:
        normalized = normalize_title(title)
        if normalized in seen_titles:
            return True
        return any(similarity(normalized, old_title) >= 0.92 for old_title in seen_titles)

    def _inside_window(self, last_seen_date: str, run_date: date) -> bool:
        try:
            last_seen = datetime.fromisoformat(last_seen_date).date()
        except ValueError:
            return False
        return run_date - last_seen <= timedelta(days=self.window_days)

    def _status_for_repeated_item(self, item: IntelItem) -> DuplicateStatus:
        text = " ".join([item.title, item.abstract or "", item.snippet or ""]).lower()
        update_terms = ["new version", "code", "github", "dataset", "benchmark", "updated", "v2"]
        if any(term in text for term in update_terms):
            return DuplicateStatus.UPDATE
        return DuplicateStatus.REPEATED
