from __future__ import annotations

from auv_intel_digest.models import IntelItem, Topic
from auv_intel_digest.scheduled_digest import FeedSource, collect_feed_sources
from auv_intel_digest.sources.base import CollectionWindow, SourceClient


class RssAtomClient(SourceClient):
    name = "rss"

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        feeds = [
            FeedSource(
                name=feed["name"],
                url=feed["url"],
                category=feed.get("category"),
                enabled=bool(feed.get("enabled", True)),
            )
            for feed in self.config.get("feeds", [])
        ]
        results = collect_feed_sources(
            feeds,
            timeout=self.timeout,
            user_agent=self.headers["User-Agent"],
            http_client=self.http_client,
        )
        items: list[IntelItem] = []
        for result in results:
            if result.status != "ok":
                continue
            for feed_item in result.items:
                if feed_item.published and not (
                    window.start.isoformat() <= feed_item.published[:10] <= window.end.isoformat()
                ):
                    continue
                items.append(
                    IntelItem(
                        title=feed_item.title,
                        authors=[],
                        source=f"rss:{feed_item.source}",
                        url=feed_item.link,
                        published_date=feed_item.published[:10] if feed_item.published else None,
                        abstract=feed_item.summary,
                        snippet=feed_item.summary,
                        tags=[feed_item.category] if feed_item.category else [],
                        raw={"guid": feed_item.guid, "feed_source": feed_item.source},
                    )
                )
        return items
