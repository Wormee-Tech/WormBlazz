from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod
from typing import Callable

from .models import (
    CrawlNetworkRequest,
    CrawlSource,
    HashtagUsage,
    RelationType,
    SocialConnection,
    SocialNetwork,
    SocialPlatform,
    SocialProfile,
)

DEFAULT_DEMO_PROFILES = 1000

_ROLE_WEIGHTS = [
    ("Person", 0.62),
    ("Creator", 0.24),
    ("Brand", 0.10),
    ("Verified", 0.04),
]

_THEMES = [
    "luna", "pixel", "saigon", "north", "orbit", "cafe", "wormee", "kai",
    "mira", "jay", "an", "delta", "echo", "nova", "coral", "atlas", "vega",
    "lotus", "hanoi", "mekong", "zen", "iris", "onyx", "ember", "sable",
]

_MENTION_RELATIONS = [
    RelationType.MENTIONS,
    RelationType.CO_MENTION,
    RelationType.SHARED_HASHTAG,
    RelationType.FOLLOWED_BY,
]

_DEMO_HASHTAGS = [
    "fyp",
    "viral",
    "creator",
    "tech",
    "travel",
    "food",
    "music",
    "fashion",
    "fitness",
    "vietnam",
    "saigon",
    "hanoi",
]


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@")


# (message, fraction in 0..1) -> None. Background jobs use it to report progress.
ProgressCallback = Callable[[str, float], None]


class SocialNetworkCrawler(ABC):
    platform: SocialPlatform

    @abstractmethod
    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        raise NotImplementedError


class DemoCrawler(SocialNetworkCrawler):
    platform = SocialPlatform.DEMO

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        if progress:
            progress("Generating demo network", 0.1)
        seed = normalize_username(request.username) or "wormee"
        # Deterministic per seed so repeated crawls are reproducible.
        rng = random.Random(f"wormblazz:{seed.casefold()}")
        count = max(1, request.max_profiles or DEFAULT_DEMO_PROFILES)

        profiles = self._profiles(seed, count, rng)
        connections = self._connections(profiles, rng)
        hashtag_usages = self._hashtags(profiles, rng)

        return SocialNetwork(
            network_id=f"demo:{seed.lower()}",
            seed_username=seed,
            platform=self.platform,
            summary=(
                f"Demo network around @{seed}: {len(profiles)} public profiles, "
                f"{len(connections)} connections. Select Instagram or TikTok after "
                "an approved API integration is configured."
            ),
            profiles=profiles,
            connections=connections,
            hashtag_usages=hashtag_usages,
        )

    @staticmethod
    def _profiles(seed: str, count: int, rng: random.Random) -> list[SocialProfile]:
        profiles: list[SocialProfile] = [
            SocialProfile(
                id=f"demo:{seed}",
                username=seed,
                display_name=seed,
                platform=SocialPlatform.DEMO,
                bio="Seed account for the WormBlazz demo",
                profile_url=f"https://www.instagram.com/{seed}/",
                follower_count=_stable_count(seed, 50_000, 500_000),
                following_count=_stable_count(seed, 200, 2_000),
                is_verified=True,
                is_private=False,
                metadata={"role": "Seed"},
            )
        ]

        used = {seed.casefold()}
        while len(profiles) < count:
            username = _make_username(rng)
            if username.casefold() in used:
                continue
            used.add(username.casefold())

            role = _pick_role(rng)
            verified = role == "Verified" or (role == "Brand" and rng.random() < 0.5)
            # ~30% private accounts so the Public/Private filter is useful in Demo.
            is_private = rng.random() < 0.30 and role not in {"Brand", "Verified"}
            profiles.append(
                SocialProfile(
                    id=f"demo:{username}",
                    username=username,
                    display_name=username.replace(".", " ").title(),
                    platform=SocialPlatform.DEMO,
                    bio=f"{role} on the WormBlazz demo network",
                    profile_url=f"https://www.instagram.com/{username}/",
                    follower_count=_stable_count(username, 300, 250_000),
                    following_count=_stable_count(username, 50, 3_000),
                    is_verified=verified,
                    is_private=is_private,
                    metadata={"role": role},
                )
            )
        return profiles

    @staticmethod
    def _connections(
        profiles: list[SocialProfile],
        rng: random.Random,
    ) -> list[SocialConnection]:
        connections: list[SocialConnection] = []
        seen: set[tuple[str, str]] = set()

        def add(source: str, target: str, relation: RelationType) -> None:
            if source == target:
                return
            key = (source, target)
            if key in seen:
                return
            seen.add(key)
            connections.append(
                SocialConnection(
                    source_profile_id=source,
                    target_profile_id=target,
                    relation=relation,
                    weight=1
                    if relation in {RelationType.FOLLOWS, RelationType.FOLLOWED_BY}
                    else 0.6,
                )
            )

        # Preferential attachment: each new profile connects to earlier, popular ones.
        degree = [1] * len(profiles)
        for index in range(1, len(profiles)):
            targets = _weighted_sample(rng, index, degree, k=min(index, rng.randint(1, 4)))
            for target_index in targets:
                add(profiles[index].id, profiles[target_index].id, RelationType.FOLLOWS)
                degree[target_index] += 1
                degree[index] += 1

        # A sprinkle of non-follow relations for a richer graph.
        extra = len(profiles) // 4
        for _ in range(extra):
            a, b = rng.randrange(len(profiles)), rng.randrange(len(profiles))
            add(profiles[a].id, profiles[b].id, rng.choice(_MENTION_RELATIONS))

        return connections

    @staticmethod
    def _hashtags(
        profiles: list[SocialProfile],
        rng: random.Random,
    ) -> list[HashtagUsage]:
        usages: list[HashtagUsage] = []
        # Cap enrichment so a 1k-node demo stays readable.
        for profile in profiles[: min(80, len(profiles))]:
            for tag in rng.sample(_DEMO_HASHTAGS, k=rng.randint(1, 3)):
                usages.append(
                    HashtagUsage(
                        profile_id=profile.id,
                        hashtag=tag,
                        post_count=rng.randint(1, 8),
                    )
                )
        return usages


class StubPlatformCrawler(SocialNetworkCrawler):
    profile_base_url: str
    integration_name: str

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        username = normalize_username(request.username)
        if not username:
            raise ValueError("Username is required.")

        prefix = "ig" if self.platform is SocialPlatform.INSTAGRAM else "tt"
        profile_id = f"{prefix}:{username}"
        return SocialNetwork(
            network_id=f"{self.platform.value.lower()}:{username.lower()}",
            seed_username=username,
            platform=self.platform,
            summary=(
                f"{self.platform.value} live collection is not configured. "
                f"Connect {self.integration_name}; WormBlazz will not bypass login, "
                "CAPTCHA, private accounts, or platform rate limits."
            ),
            profiles=[
                SocialProfile(
                    id=profile_id,
                    username=username,
                    display_name=username,
                    platform=self.platform,
                    profile_url=self.profile_base_url.format(username=username),
                    bio="API adapter is ready; live public data is not configured.",
                    metadata={"role": "Seed", "status": "stub"},
                )
            ],
        )


class InstagramCrawler(StubPlatformCrawler):
    """Legacy stub kept for tests; production uses InstagramApifyCrawler."""

    platform = SocialPlatform.INSTAGRAM
    profile_base_url = "https://www.instagram.com/{username}/"
    integration_name = "Apify (set APIFY_TOKEN)"


class TikTokCrawler(StubPlatformCrawler):
    """Legacy stub kept for tests; production uses TikTokApifyCrawler."""
    platform = SocialPlatform.TIKTOK
    profile_base_url = "https://www.tiktok.com/@{username}"
    integration_name = "the TikTok Research or Display API"


def default_crawlers() -> dict[tuple[SocialPlatform, CrawlSource], SocialNetworkCrawler]:
    from .apify_instagram import InstagramApifyCrawler
    from .apify_tiktok import TikTokApifyCrawler
    from .local_scraper import LocalInstagramCrawler, LocalTikTokCrawler

    demo = DemoCrawler()
    return {
        (SocialPlatform.DEMO, CrawlSource.APIFY): demo,
        (SocialPlatform.DEMO, CrawlSource.LOCAL): demo,
        (SocialPlatform.INSTAGRAM, CrawlSource.APIFY): InstagramApifyCrawler(),
        (SocialPlatform.INSTAGRAM, CrawlSource.LOCAL): LocalInstagramCrawler(),
        (SocialPlatform.TIKTOK, CrawlSource.APIFY): TikTokApifyCrawler(),
        (SocialPlatform.TIKTOK, CrawlSource.LOCAL): LocalTikTokCrawler(),
    }


def _make_username(rng: random.Random) -> str:
    theme = rng.choice(_THEMES)
    suffix = rng.choice(["creates", "lens", "beats", "frame", "studio", "codes",
                          "daily", "hub", "world", "vibes", "media", "art"])
    return f"{theme}.{suffix}{rng.randint(1, 999)}"


def _pick_role(rng: random.Random) -> str:
    roll = rng.random()
    cumulative = 0.0
    for role, weight in _ROLE_WEIGHTS:
        cumulative += weight
        if roll <= cumulative:
            return role
    return _ROLE_WEIGHTS[0][0]


def _weighted_sample(
    rng: random.Random,
    upper: int,
    degree: list[int],
    k: int,
) -> list[int]:
    """Sample up to k distinct indices in [0, upper) weighted by current degree."""
    picks: set[int] = set()
    attempts = 0
    total = sum(degree[:upper]) or 1
    while len(picks) < k and attempts < k * 6:
        attempts += 1
        threshold = rng.uniform(0, total)
        cursor = 0.0
        for candidate in range(upper):
            cursor += degree[candidate]
            if cursor >= threshold:
                picks.add(candidate)
                break
    if not picks:
        picks.add(rng.randrange(upper))
    return list(picks)


def _stable_count(key: str, minimum: int, maximum: int) -> int:
    digest = hashlib.sha256(key.encode()).digest()
    value = int.from_bytes(digest[:8], "big")
    return minimum + value % (maximum - minimum)

