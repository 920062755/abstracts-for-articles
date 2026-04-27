from __future__ import annotations

from auv_intel_digest.models import IntelItem, Topic
from auv_intel_digest.sources.base import (
    CollectionWindow,
    SourceClient,
    all_topic_queries,
    clean_text,
    date_from_parts,
)


class CrossrefClient(SourceClient):
    name = "crossref"
    endpoint = "https://api.crossref.org/works"

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        items: list[IntelItem] = []
        with self.managed_client() as client:
            for _topic, query in all_topic_queries(topics):
                params = {
                    "query": query,
                    "filter": f"from-pub-date:{window.start.isoformat()},until-pub-date:{window.end.isoformat()}",
                    "rows": self.max_results,
                }
                if self.settings.contact_email:
                    params["mailto"] = self.settings.contact_email
                response = client.get(self.endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                items.extend(self._parse(data))
        return items

    def _parse(self, data: dict) -> list[IntelItem]:
        items = []
        for work in data.get("message", {}).get("items", []):
            title = clean_text(" ".join(work.get("title") or [])) or ""
            authors = [
                " ".join(part for part in [author.get("given"), author.get("family")] if part)
                for author in work.get("author", [])
            ]
            published = work.get("published-print") or work.get("published-online") or work.get("issued")
            items.append(
                IntelItem(
                    title=title,
                    authors=[author for author in authors if author],
                    source=self.name,
                    url=work.get("URL") or "",
                    published_date=date_from_parts(published.get("date-parts") if published else None),
                    abstract=clean_text(work.get("abstract")),
                    doi=work.get("DOI"),
                    raw={"type": work.get("type"), "publisher": work.get("publisher")},
                )
            )
        return items
