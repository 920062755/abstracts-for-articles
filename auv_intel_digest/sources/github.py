from __future__ import annotations

from auv_intel_digest.models import IntelItem, Topic
from auv_intel_digest.sources.base import CollectionWindow, SourceClient, all_topic_queries, env_value


class GitHubClient(SourceClient):
    name = "github"
    endpoint = "https://api.github.com/search/repositories"

    def fetch(self, topics: list[Topic], window: CollectionWindow) -> list[IntelItem]:
        items: list[IntelItem] = []
        headers = dict(self.headers)
        token = self.settings.github_token or env_value(self.config.get("token_env"))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"

        min_stars = int(self.config.get("min_stars", 0))
        search_config = self.config.get("search") or {}
        with self.managed_client() as client:
            for _topic, query in all_topic_queries(topics):
                response = client.get(
                    self.endpoint,
                    params={
                        "q": f"({query}) pushed:>={window.start.isoformat()} stars:>={min_stars}",
                        "sort": search_config.get("sort", "updated"),
                        "order": search_config.get("order", "desc"),
                        "per_page": self.max_results,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                items.extend(self._parse(response.json()))
        return items

    def _parse(self, data: dict) -> list[IntelItem]:
        items = []
        for repo in data.get("items", []):
            pushed_at = repo.get("pushed_at") or repo.get("updated_at") or ""
            tags = list(repo.get("topics") or [])
            items.append(
                IntelItem(
                    title=repo.get("full_name") or repo.get("name") or "",
                    authors=[repo.get("owner", {}).get("login", "")],
                    source=self.name,
                    url=repo.get("html_url") or "",
                    published_date=pushed_at[:10] if pushed_at else None,
                    abstract=repo.get("description"),
                    snippet=(
                        f"GitHub repository with {repo.get('stargazers_count', 0)} stars, "
                        f"updated {pushed_at[:10] if pushed_at else 'unknown'}."
                    ),
                    tags=[tag for tag in tags if tag],
                    raw={
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language"),
                    },
                )
            )
        return items
