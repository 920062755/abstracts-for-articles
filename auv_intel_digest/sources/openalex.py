from __future__ import annotations

from auv_intel_digest.models import IntelItem, Topic
from auv_intel_digest.sources.base import CollectionWindow, SourceClient, all_topic_queries, clean_text


class OpenAlexClient(SourceClient):
    name = "openalex"
    endpoint = "https://api.openalex.org/works"

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        items: list[IntelItem] = []
        with self.managed_client() as client:
            for _topic, query in all_topic_queries(topics):
                params = {
                    "search": query,
                    "filter": (
                        f"from_publication_date:{window.start.isoformat()},"
                        f"to_publication_date:{window.end.isoformat()}"
                    ),
                    "per-page": self.max_results,
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
        for work in data.get("results", []):
            title = clean_text(work.get("title")) or ""
            authors = [
                authorship.get("author", {}).get("display_name", "")
                for authorship in work.get("authorships", [])
            ]
            primary_location = work.get("primary_location") or {}
            landing_page = primary_location.get("landing_page_url")
            url = landing_page or work.get("doi") or work.get("id") or ""
            items.append(
                IntelItem(
                    title=title,
                    authors=[author for author in authors if author],
                    source=self.name,
                    url=url,
                    published_date=work.get("publication_date"),
                    abstract=self._abstract(work.get("abstract_inverted_index")),
                    doi=(work.get("doi") or "").removeprefix("https://doi.org/") or None,
                    raw={"openalex_id": work.get("id"), "type": work.get("type")},
                )
            )
        return items

    @staticmethod
    def _abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
        if not inverted_index:
            return None
        positions: list[tuple[int, str]] = []
        for word, indexes in inverted_index.items():
            positions.extend((index, word) for index in indexes)
        return " ".join(word for _index, word in sorted(positions))
