from __future__ import annotations

from collections import Counter, deque

from .models import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStatsResponse,
    NetworkOverviewResponse,
    SocialNetwork,
    SocialProfile,
)


def profile_node_type(profile: SocialProfile) -> str:
    return profile.metadata.get("role") or ("Verified" if profile.is_verified else "Person")


def to_graph(network: SocialNetwork) -> GraphResponse:
    nodes = []
    for profile in network.profiles:
        profile_url = _public_profile_url(profile)
        visibility = "Private" if profile.is_private else "Public"
        metadata = {
            **profile.metadata,
            "username": profile.username,
            "platform": profile.platform.value,
            "profileUrl": profile_url or "",
            "verified": str(profile.is_verified).lower(),
            "isPrivate": str(profile.is_private).lower(),
            "visibility": visibility,
            "filePath": f"@{profile.username.lstrip('@')}",
        }
        if profile.bio:
            metadata["bio"] = profile.bio
        if profile.avatar_url:
            metadata["avatarUrl"] = profile.avatar_url
        if profile.follower_count is not None:
            metadata["followers"] = str(profile.follower_count)
        if profile.following_count is not None:
            metadata["following"] = str(profile.following_count)

        nodes.append(
            GraphNode(
                id=profile.id,
                name=profile.display_name or profile.username,
                type=profile_node_type(profile),
                metadata=metadata,
            )
        )

    edges = [
        GraphEdge(
            source=connection.source_profile_id,
            target=connection.target_profile_id,
            relationship=connection.relation.value,
        )
        for connection in network.connections
    ]

    hashtags: dict[str, int] = Counter()
    for usage in network.hashtag_usages:
        tag = _normalize_hashtag(usage.hashtag)
        if not tag:
            continue
        hashtags[tag] += usage.post_count
        edges.append(
            GraphEdge(
                source=usage.profile_id,
                target=f"hashtag:{tag.casefold()}",
                relationship="UsesHashtag",
            )
        )

    nodes.extend(
        GraphNode(
            id=f"hashtag:{tag.casefold()}",
            name=f"#{tag}",
            type="Hashtag",
            metadata={
                "hashtag": tag,
                "usageCount": str(count),
                "platform": network.platform.value,
                "linkType": "Hashtag",
                "profileUrl": _hashtag_url(network.platform.value, tag),
                "visibility": "Public",
                "isPrivate": "false",
            },
        )
        for tag, count in hashtags.items()
    )
    return GraphResponse(nodes=nodes, edges=edges)


def to_overview(network: SocialNetwork) -> NetworkOverviewResponse:
    degree: Counter[str] = Counter()
    for connection in network.connections:
        degree[connection.source_profile_id] += 1
        degree[connection.target_profile_id] += 1

    by_id = {profile.id: profile for profile in network.profiles}
    top_connected = [
        f"{by_id[profile_id].username} ({count})"
        for profile_id, count in degree.most_common(8)
        if profile_id in by_id
    ]
    public_count = sum(1 for profile in network.profiles if not profile.is_private)
    private_count = len(network.profiles) - public_count
    return NetworkOverviewResponse(
        network_id=network.network_id,
        seed_username=network.seed_username,
        platform=network.platform.value,
        profile_count=len(network.profiles),
        connection_count=len(network.connections),
        public_count=public_count,
        private_count=private_count,
        hashtag_count=len({_normalize_hashtag(u.hashtag) for u in network.hashtag_usages if _normalize_hashtag(u.hashtag)}),
        summary=network.summary,
        top_connected=top_connected,
    )


def to_stats(network: SocialNetwork) -> GraphStatsResponse:
    ids = {profile.id for profile in network.profiles}
    sources = {connection.source_profile_id for connection in network.connections}
    targets = {connection.target_profile_id for connection in network.connections}
    names = {profile.id: profile.username for profile in network.profiles}

    graph = to_graph(network)
    return GraphStatsResponse(
        total_nodes=len(graph.nodes),
        total_edges=len(graph.edges),
        node_type_counts=dict(Counter(node.type for node in graph.nodes)),
        edge_type_counts=dict(Counter(edge.relationship for edge in graph.edges)),
        max_depth=_max_depth(network),
        root_nodes=[names[node_id] for node_id in sorted(ids - targets)[:20]],
        leaf_nodes=[names[node_id] for node_id in sorted(ids - sources)[:20]],
    )


def _max_depth(network: SocialNetwork) -> int:
    seed = next(
        (
            profile
            for profile in network.profiles
            if profile.username.casefold() == network.seed_username.casefold()
        ),
        None,
    )
    if seed is None:
        return 0

    adjacency: dict[str, list[str]] = {}
    for connection in network.connections:
        adjacency.setdefault(connection.source_profile_id, []).append(
            connection.target_profile_id
        )
        # Social graphs are effectively undirected for "how far from seed".
        adjacency.setdefault(connection.target_profile_id, []).append(
            connection.source_profile_id
        )

    queue = deque([(seed.id, 0)])
    visited = {seed.id}
    maximum = 0
    while queue:
        current, depth = queue.popleft()
        maximum = max(maximum, depth)
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return maximum


def _public_profile_url(profile: SocialProfile) -> str | None:
    """Public profile URL for live platforms only. Demo never deep-links out."""
    handle = profile.username.strip().lstrip("@")
    if not handle:
        return None

    platform = profile.platform.value
    # Synthetic demo handles do not exist on Instagram — avoid 404 deep links.
    if platform == "Demo":
        return None
    if platform == "Instagram":
        return f"https://www.instagram.com/{handle}/"
    if platform == "TikTok":
        return f"https://www.tiktok.com/@{handle}"

    raw = (profile.profile_url or "").strip()
    if not raw or "example.com" in raw:
        return None

    return raw.replace(f"instagram.com/@{handle}", f"instagram.com/{handle}")


def _normalize_hashtag(value: str) -> str:
    return value.strip().lstrip("#").strip().lower()


def _hashtag_url(platform: str, tag: str) -> str:
    if platform == "TikTok":
        return f"https://www.tiktok.com/tag/{tag}"
    if platform == "Instagram":
        return f"https://www.instagram.com/explore/tags/{tag}/"
    return ""

