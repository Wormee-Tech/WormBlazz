import os

from fastapi.testclient import TestClient

from wormblazz.main import create_app


def client(tmp_path) -> TestClient:
    return TestClient(create_app(cache_dir=tmp_path, frontend_dir=tmp_path / "missing"))


def test_health(tmp_path) -> None:
    response = client(tmp_path).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_network_flow(tmp_path) -> None:
    api = client(tmp_path)
    crawl = api.post(
        "/api/network/crawl",
        json={
            "username": "@wormee",
            "platform": "Demo",
            "depth": 2,
            "maxProfiles": 40,
        },
    )
    assert crawl.status_code == 200
    assert crawl.json() == {"networkId": "demo:wormee", "status": "completed"}

    graph = api.get("/api/network/demo%3Awormee/graph")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) > 5
    assert len(graph.json()["edges"]) > 5
    # Demo must not deep-link to Instagram (handles are synthetic).
    assert not graph.json()["nodes"][0]["metadata"].get("profileUrl")
    visibilities = {node["metadata"]["visibility"] for node in graph.json()["nodes"]}
    assert "Public" in visibilities
    assert "Private" in visibilities
    overview = api.get("/api/network/demo%3Awormee/overview")
    assert overview.status_code == 200
    assert overview.json()["seedUsername"] == "wormee"
    hashtag_nodes = [node for node in graph.json()["nodes"] if node["type"] == "Hashtag"]
    assert overview.json()["profileCount"] + len(hashtag_nodes) == len(graph.json()["nodes"])
    assert overview.json()["hashtagCount"] == len(hashtag_nodes)
    assert overview.json()["publicCount"] + overview.json()["privateCount"] == overview.json()[
        "profileCount"
    ]
    assert overview.json()["privateCount"] > 0

    stats = api.get("/api/network/demo%3Awormee/graph/stats")
    assert stats.status_code == 200
    assert stats.json()["totalNodes"] == len(graph.json()["nodes"])
    assert "Seed" in stats.json()["nodeTypeCounts"]


def test_tiktok_requires_apify_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    api = client(tmp_path)
    response = api.post(
        "/api/network/crawl",
        json={"username": "public.user", "platform": "TikTok"},
    )
    assert response.status_code == 400
    assert "APIFY_TOKEN" in response.json()["detail"]


def test_demo_seed_does_not_duplicate_known_handle(tmp_path) -> None:
    api = client(tmp_path)
    crawl = api.post(
        "/api/network/crawl",
        json={"username": "luna.creates", "platform": "Demo", "depth": 3},
    )
    network_id = crawl.json()["networkId"]
    nodes = api.get(f"/api/network/{network_id}/graph").json()["nodes"]
    node_ids = [node["id"] for node in nodes]
    assert len(node_ids) == len(set(node_ids))


def test_instagram_requires_apify_token(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    api = client(tmp_path)
    response = api.post(
        "/api/network/crawl",
        json={"username": "instagram", "platform": "Instagram", "maxProfiles": 10},
    )
    assert response.status_code == 400
    assert "APIFY_TOKEN" in response.json()["detail"]


def test_invalid_request(tmp_path) -> None:
    response = client(tmp_path).post(
        "/api/network/crawl",
        json={"username": "wormee", "platform": "Demo", "depth": 99},
    )
    assert response.status_code == 422


def test_unknown_network(tmp_path) -> None:
    response = client(tmp_path).get("/api/network/missing/graph")
    assert response.status_code == 404


def test_instagram_apify_maps_followers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APIFY_TOKEN", "test-token")

    from wormblazz.apify_instagram import InstagramApifyCrawler
    from wormblazz.models import CrawlNetworkRequest
    import asyncio

    async def fake_fetch(self, username: str, limit: int):
        return [
            {
                "username": "follower_one",
                "full_name": "Follower One",
                "is_verified": True,
                "follower_count": 12,
                "is_private": False,
            },
            {
                "username": "follower_two",
                "fullName": "Follower Two",
                "isVerified": False,
                "isPrivate": True,
            },
        ][:limit]

    monkeypatch.setattr(InstagramApifyCrawler, "_fetch_followers", fake_fetch)
    crawler = InstagramApifyCrawler(token="test-token")
    network = asyncio.run(
        crawler.crawl(
            CrawlNetworkRequest(
                username="seeduser",
                platform="Instagram",
                max_profiles=1000,
            )
        )
    )
    assert network.seed_username == "seeduser"
    assert len(network.profiles) == 3
    assert len(network.connections) == 2
    assert any(profile.is_private for profile in network.profiles)
    assert all(
        profile.profile_url.startswith("https://www.instagram.com/")
        for profile in network.profiles
    )


def test_tiktok_apify_maps_followers_and_hashtags(monkeypatch) -> None:
    import asyncio

    from wormblazz.apify_tiktok import TikTokApifyCrawler
    from wormblazz.graph import to_graph
    from wormblazz.models import CrawlNetworkRequest

    async def fake_followers(self, username: str, limit: int):
        return [
            {
                "recordType": "relationship",
                "username": "creator_one",
                "displayName": "Creator One",
                "profilePictureUrl": "https://cdn.example/avatar.jpg",
                "followersCount": 120,
                "followingCount": 30,
                "isVerified": True,
                "accountPrivate": False,
            },
            {
                "recordType": "relationship",
                "username": "private_creator",
                "accountPrivate": True,
            },
        ][:limit]

    async def fake_posts(self, usernames: list[str]):
        return [
            {
                "authorMeta": {"name": "creator_one"},
                "text": "New post #Tech #FYP",
                "hashtags": [{"name": "tech"}, {"name": "creator"}],
            },
            {
                "authorMeta": {"name": "creator_one"},
                "text": "#tech again",
                "hashtags": [],
            },
        ]

    monkeypatch.setattr(TikTokApifyCrawler, "_fetch_followers", fake_followers)
    monkeypatch.setattr(TikTokApifyCrawler, "_fetch_posts", fake_posts)
    crawler = TikTokApifyCrawler(token="test-token")
    network = asyncio.run(
        crawler.crawl(
            CrawlNetworkRequest(
                username="@seed",
                platform="TikTok",
                maxProfiles=1000,
            )
        )
    )

    assert len(network.profiles) == 3
    assert any(profile.is_private for profile in network.profiles)
    usages = {(usage.hashtag, usage.post_count) for usage in network.hashtag_usages}
    assert ("tech", 2) in usages
    assert ("fyp", 1) in usages
    graph = to_graph(network)
    assert any(node.type == "Hashtag" and node.name == "#tech" for node in graph.nodes)
    assert any(edge.relationship == "UsesHashtag" for edge in graph.edges)


def test_local_instagram_bfs_and_hashtags() -> None:
    import asyncio

    from wormblazz.local_scraper import LocalInstagramCrawler
    from wormblazz.models import CrawlNetworkRequest

    pages = {
        "seeduser": {
            "full_name": "Seed User",
            "biography": "collab with @friend_one #vietnam",
            "is_verified": True,
            "is_private": False,
            "edge_followed_by": {"count": 999},
            "edge_related_profiles": {
                "edges": [{"node": {"username": "related_two"}}]
            },
            "edge_owner_to_timeline_media": {
                "edges": [
                    {
                        "node": {
                            "edge_media_to_caption": {
                                "edges": [{"node": {"text": "post ft @friend_one #travel"}}]
                            }
                        }
                    }
                ]
            },
        },
        "friend_one": {
            "full_name": "Friend One",
            "biography": "hi #travel",
            "is_private": False,
            "edge_owner_to_timeline_media": {"edges": []},
        },
        "related_two": {
            "full_name": "Related Two",
            "biography": "",
            "is_private": True,
            "edge_owner_to_timeline_media": {"edges": []},
        },
    }

    async def fake_fetch(self, client, username: str):
        return pages.get(username.casefold())

    crawler = LocalInstagramCrawler(request_delay=0, max_nodes=50)
    crawler._fetch_profile = fake_fetch.__get__(crawler, LocalInstagramCrawler)
    network = asyncio.run(
        crawler.crawl(CrawlNetworkRequest(username="@seeduser", platform="Instagram", source="local", depth=2))
    )

    usernames = {p.username.casefold() for p in network.profiles}
    assert {"seeduser", "friend_one", "related_two"} <= usernames
    relations = {c.relation.value for c in network.connections}
    assert "Mentions" in relations
    assert "Related" in relations
    tags = {u.hashtag for u in network.hashtag_usages}
    assert {"vietnam", "travel"} <= tags
    # @friend_one mentioned in bio and caption -> aggregated, not duplicated.
    assert sum(1 for c in network.connections if c.relation.value == "Mentions") >= 1


def test_instagram_og_meta_helpers() -> None:
    from wormblazz.local_scraper import (
        _display_name_from_og_title,
        _instagram_bio_from_description,
        _parse_html_meta,
        _parse_instagram_og_counts,
    )

    html = """
    <html><head>
    <title>VTV DIGITAL (&#064;vtv24news) • Instagram</title>
    <meta property="og:title" content="VTV DIGITAL (&#064;vtv24news) • Instagram photos and videos" />
    <meta property="og:description" content="447K Followers, 97 Following, 32K Posts - See Instagram photos and videos from VTV DIGITAL (&#064;vtv24news)" />
    <meta name="description" content="447K Followers, 97 Following, 32K Posts - VTV DIGITAL (&#064;vtv24news) on Instagram: &quot;News channel @vtv.go #news #vietnam&quot;" />
    </head></html>
    """
    meta = _parse_html_meta(html)
    assert "vtv24news" in meta["og:title"]
    assert _display_name_from_og_title(meta["og:title"], "vtv24news") == "VTV DIGITAL"
    followers, following = _parse_instagram_og_counts(meta["og:description"])
    assert followers == 447_000
    assert following == 97
    bio = _instagram_bio_from_description(meta["description"])
    assert "@vtv.go" in bio
    assert "#news" in bio


def test_local_instagram_uses_bot_ua_no_login(monkeypatch) -> None:
    import asyncio

    from wormblazz.local_scraper import LocalInstagramCrawler
    from wormblazz.models import CrawlNetworkRequest

    seen_headers: dict[str, str] = {}

    html = (
        "<html><head>"
        "<title>VTV DIGITAL (@vtv24news)</title>"
        '<meta property="og:title" content="VTV DIGITAL (@vtv24news) • Instagram photos and videos" />'
        '<meta property="og:url" content="https://www.instagram.com/vtv24news/" />'
        '<meta property="og:description" content="447K Followers, 97 Following, 32K Posts - See Instagram photos and videos from VTV DIGITAL (@vtv24news)" />'
        '<meta name="description" content="447K Followers, 97 Following, 32K Posts - VTV DIGITAL (@vtv24news) on Instagram: &quot;Collab with @partner_news #breaking&quot;" />'
        "</head></html>"
    )

    class FakeResponse:
        status_code = 200
        text = html

    class FakeClient:
        async def get(self, url, headers=None):
            seen_headers.update(headers or {})
            return FakeResponse()

    async def fake_fetch(self, client, username):
        # Delegate to the real HTML parser against our fake client.
        return await LocalInstagramCrawler._fetch_from_html(self, FakeClient(), username)

    monkeypatch.setattr(LocalInstagramCrawler, "_fetch_profile", fake_fetch)

    crawler = LocalInstagramCrawler(request_delay=0, session_id="", cookies="")
    network = asyncio.run(
        crawler.crawl(
            CrawlNetworkRequest(username="vtv24news", platform="Instagram", source="local", depth=1)
        )
    )

    assert "facebookexternalhit" in seen_headers.get("User-Agent", "")
    assert "Cookie" not in seen_headers
    seed = next(p for p in network.profiles if p.username == "vtv24news")
    assert seed.follower_count == 447_000
    assert seed.following_count == 97
    # Bio mention expands the graph; hashtag becomes a node.
    assert any(p.username == "partner_news" for p in network.profiles)
    assert any(u.hashtag == "breaking" for u in network.hashtag_usages)


def test_local_instagram_seed_unreadable_errors() -> None:
    import asyncio

    from wormblazz.local_scraper import LocalInstagramCrawler
    from wormblazz.models import CrawlNetworkRequest

    async def fake_fetch(self, client, username: str):
        return None

    crawler = LocalInstagramCrawler(request_delay=0, session_id="", cookies="")
    crawler._fetch_profile = fake_fetch.__get__(crawler, LocalInstagramCrawler)

    try:
        asyncio.run(
            crawler.crawl(
                CrawlNetworkRequest(username="ghost", platform="Instagram", source="local")
            )
        )
    except ValueError as error:
        assert "could not read public data" in str(error).casefold()
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for unreadable seed")


def test_local_source_uses_separate_cache_slot(tmp_path, monkeypatch) -> None:
    from wormblazz.models import CrawlNetworkRequest
    from wormblazz.service import NetworkService

    apify = CrawlNetworkRequest(username="abc", platform="Instagram", source="apify")
    local = CrawlNetworkRequest(username="abc", platform="Instagram", source="local")
    assert NetworkService.network_id_for(apify, "abc") == "instagram:abc"
    assert NetworkService.network_id_for(local, "abc") == "instagram:local:abc"


def test_background_job_completes(tmp_path) -> None:
    api = client(tmp_path)
    start = api.post(
        "/api/network/crawl/background",
        json={"username": "wormee", "platform": "Demo", "depth": 2, "maxProfiles": 30},
    )
    assert start.status_code == 200
    job_id = start.json()["jobId"]

    # TestClient runs the event loop per-request; poll until the task settles.
    final = None
    for _ in range(50):
        final = api.get(f"/api/network/jobs/{job_id}").json()
        if final["status"] in {"succeeded", "failed"}:
            break
    assert final is not None
    assert final["status"] == "succeeded"
    assert final["networkId"] == "demo:wormee"

    graph = api.get(f"/api/network/{final['networkId']}/graph")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) > 5
