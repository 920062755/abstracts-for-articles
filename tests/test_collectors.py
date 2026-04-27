from datetime import date

import httpx

from auv_intel_digest.models import Topic
from auv_intel_digest.settings import Settings
from auv_intel_digest.sources.arxiv import ArxivClient
from auv_intel_digest.sources.base import CollectionWindow
from auv_intel_digest.sources.crossref import CrossrefClient
from auv_intel_digest.sources.github import GitHubClient
from auv_intel_digest.sources.openalex import OpenAlexClient


def _topic():
    return Topic(
        key="multi_agent_planning",
        name_zh="多智能体协同规划",
        name_en="Multi-Agent Cooperative Planning",
        enabled=True,
        weight=1.0,
        keywords={
            "en": {
                "positive": ["multi-agent planning"],
                "required_any": ["multi-agent"],
                "negative": [],
            }
        },
        tags=["planning"],
    )


def _settings():
    return Settings(contact_email="test@example.com", github_token="ghp_test")


def _window():
    return CollectionWindow(date(2026, 4, 26), date(2026, 4, 27))


def test_arxiv_collector_parses_atom_response():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2604.00001v1</id>
        <updated>2026-04-27T00:00:00Z</updated>
        <published>2026-04-27T00:00:00Z</published>
        <title>Multi-AUV cooperative planning</title>
        <summary>A cooperative planning method for AUV teams.</summary>
        <author><name>Alice</name></author>
        <arxiv:doi>10.1234/example</arxiv:doi>
      </entry>
    </feed>"""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=xml))
    client = httpx.Client(transport=transport)

    items = ArxivClient(
        {"enabled": True, "max_results": 1, "categories": ["cs.RO"]},
        _settings(),
        {},
        http_client=client,
    ).fetch([_topic()], _window())

    assert items[0].source == "arxiv"
    assert items[0].arxiv_id == "2604.00001v1"
    assert items[0].doi == "10.1234/example"


def test_openalex_collector_parses_work_response():
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Multi-agent planning for underwater robots",
                "publication_date": "2026-04-27",
                "doi": "https://doi.org/10.1000/openalex",
                "authorships": [{"author": {"display_name": "Bob"}}],
                "primary_location": {"landing_page_url": "https://paper.test"},
                "abstract_inverted_index": {"Planning": [0], "works": [1]},
                "type": "article",
            }
        ]
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = httpx.Client(transport=transport)

    items = OpenAlexClient({"enabled": True, "max_results": 1}, _settings(), {}, client).fetch(
        [_topic()], _window()
    )

    assert items[0].source == "openalex"
    assert items[0].authors == ["Bob"]
    assert items[0].abstract == "Planning works"
    assert items[0].doi == "10.1000/openalex"


def test_crossref_collector_parses_work_response():
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Pursuit evasion planning"],
                    "author": [{"given": "Carol", "family": "Chen"}],
                    "URL": "https://doi.org/10.1000/crossref",
                    "DOI": "10.1000/crossref",
                    "published-online": {"date-parts": [[2026, 4, 27]]},
                    "abstract": "<jats:p>Abstract text.</jats:p>",
                    "type": "journal-article",
                }
            ]
        }
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = httpx.Client(transport=transport)

    items = CrossrefClient({"enabled": True, "max_results": 1}, _settings(), {}, client).fetch(
        [_topic()], _window()
    )

    assert items[0].source == "crossref"
    assert items[0].published_date == "2026-04-27"
    assert items[0].abstract == "Abstract text."


def test_github_collector_parses_repository_response_and_uses_token():
    seen_auth = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "full_name": "lab/multi-auv-planner",
                        "owner": {"login": "lab"},
                        "html_url": "https://github.com/lab/multi-auv-planner",
                        "pushed_at": "2026-04-27T01:00:00Z",
                        "description": "Multi-AUV cooperative planning code.",
                        "topics": ["auv", "planning"],
                        "stargazers_count": 42,
                        "forks_count": 3,
                        "language": "Python",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    items = GitHubClient(
        {"enabled": True, "max_results": 1, "min_stars": 5, "search": {"sort": "updated"}},
        _settings(),
        {},
        client,
    ).fetch([_topic()], _window())

    assert seen_auth["authorization"] == "Bearer ghp_test"
    assert items[0].source == "github"
    assert items[0].published_date == "2026-04-27"
    assert items[0].raw["stars"] == 42
