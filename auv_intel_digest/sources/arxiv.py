from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from auv_intel_digest.models import IntelItem, Topic
from auv_intel_digest.sources.base import CollectionWindow, SourceClient, all_topic_queries, clean_text


class ArxivClient(SourceClient):
    name = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        items: list[IntelItem] = []
        with self.managed_client() as client:
            for _topic, query in all_topic_queries(topics):
                response = client.get(
                    self.endpoint,
                    params={
                        "search_query": self._search_query(query),
                        "start": 0,
                        "max_results": self.max_results,
                        "sortBy": self.config.get("sort_by", "submittedDate"),
                        "sortOrder": "descending",
                    },
                )
                response.raise_for_status()
                items.extend(self._parse(response.text, window))
        return items

    def _search_query(self, query: str) -> str:
        categories = self.config.get("categories") or []
        term_query = " OR ".join(f'all:"{term.strip()}"' for term in query.split(" OR ") if term.strip())
        if not categories:
            return term_query
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        return f"({term_query}) AND ({category_query})"

    def _parse(self, xml_text: str, window: CollectionWindow) -> list[IntelItem]:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_text)
        items: list[IntelItem] = []
        for entry in root.findall("atom:entry", ns):
            published = self._text(entry, "atom:published", ns)
            published_date = published[:10] if published else None
            if published_date and not (window.start.isoformat() <= published_date <= window.end.isoformat()):
                continue

            url = self._text(entry, "atom:id", ns) or ""
            title = clean_text(self._text(entry, "atom:title", ns)) or ""
            summary = clean_text(self._text(entry, "atom:summary", ns))
            authors = [
                clean_text(author.findtext("atom:name", namespaces=ns)) or ""
                for author in entry.findall("atom:author", ns)
            ]
            doi = self._text(entry, "arxiv:doi", ns)
            items.append(
                IntelItem(
                    title=title,
                    authors=[author for author in authors if author],
                    source=self.name,
                    url=url,
                    published_date=published_date,
                    abstract=summary,
                    doi=doi,
                    arxiv_id=self._arxiv_id(url),
                    raw={"source_id": url},
                )
            )
        return items

    @staticmethod
    def _text(entry: ET.Element, path: str, ns: dict[str, str]) -> str | None:
        value = entry.findtext(path, namespaces=ns)
        return value.strip() if value else None

    @staticmethod
    def _arxiv_id(url: str) -> str | None:
        match = re.search(r"/abs/([^/?#]+)", url)
        return match.group(1) if match else None
