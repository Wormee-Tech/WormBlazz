from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class SocialPlatform(str, Enum):
    DEMO = "Demo"
    INSTAGRAM = "Instagram"
    TIKTOK = "TikTok"


class RelationType(str, Enum):
    FOLLOWS = "Follows"
    FOLLOWED_BY = "FollowedBy"
    MENTIONS = "Mentions"
    CO_MENTION = "CoMention"
    SHARED_HASHTAG = "SharedHashtag"
    USES_HASHTAG = "UsesHashtag"
    RELATED = "Related"


class CrawlSource(str, Enum):
    """Where profile data comes from."""

    APIFY = "apify"  # paid third-party actors (fast, complete)
    LOCAL = "local"  # self-hosted background scraper (free, best-effort)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CrawlNetworkRequest(ApiModel):
    username: str = "wormee"
    platform: SocialPlatform = SocialPlatform.DEMO
    source: CrawlSource = CrawlSource.APIFY
    depth: int = Field(default=3, ge=1, le=6)
    max_profiles: int = Field(default=1000, ge=1, le=5000)
    force_refresh: bool = False


class CrawlNetworkResponse(ApiModel):
    network_id: str
    status: str = "completed"


class CrawlJob(ApiModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    message: str = ""
    network_id: str | None = None
    error: str | None = None


class SocialProfile(ApiModel):
    id: str
    username: str
    platform: SocialPlatform
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    is_verified: bool = False
    is_private: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class SocialConnection(ApiModel):
    source_profile_id: str
    target_profile_id: str
    relation: RelationType
    weight: float = 1
    metadata: dict[str, str] = Field(default_factory=dict)


class HashtagUsage(ApiModel):
    profile_id: str
    hashtag: str
    post_count: int = Field(default=1, ge=1)


class SocialNetwork(ApiModel):
    network_id: str
    seed_username: str
    platform: SocialPlatform
    summary: str = ""
    profiles: list[SocialProfile] = Field(default_factory=list)
    connections: list[SocialConnection] = Field(default_factory=list)
    hashtag_usages: list[HashtagUsage] = Field(default_factory=list)


class GraphNode(ApiModel):
    id: str
    name: str
    type: str
    metadata: dict[str, str] = Field(default_factory=dict)


class GraphEdge(ApiModel):
    source: str
    target: str
    relationship: str


class GraphResponse(ApiModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphStatsResponse(ApiModel):
    total_nodes: int
    total_edges: int
    node_type_counts: dict[str, int]
    edge_type_counts: dict[str, int]
    max_depth: int
    root_nodes: list[str]
    leaf_nodes: list[str]


class NetworkOverviewResponse(ApiModel):
    network_id: str
    seed_username: str
    platform: str
    profile_count: int
    connection_count: int
    public_count: int = 0
    private_count: int = 0
    hashtag_count: int = 0
    summary: str
    top_connected: list[str]

