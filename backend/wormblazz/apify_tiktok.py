from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any

from .apify_client import run_actor
from .crawlers import ProgressCallback, SocialNetworkCrawler, normalize_username
from .models import (
    CrawlNetworkRequest,
    HashtagUsage,
    RelationType,
    SocialConnection,
    SocialNetwork,
    SocialPlatform,
    SocialProfile,
)


DEFAULT_FOLLOWERS_ACTOR = "coregent~tiktok-followers-following-scraper"
DEFAULT_POSTS_ACTOR = "clockworks~tiktok-scraper"
HASHTAG_PROFILE_LIMIT = 20
POSTS_PER_PROFILE = 5


class TikTokApifyCrawler(SocialNetworkCrawler):
    platform = SocialPlatform.TIKTOK

    def __init__(
        self,
        token: str | None = None,
        followers_actor: str | None = None,
        posts_actor: str | None = None,
    ) -> None:
        self.token = token if token is not None else os.getenv("APIFY_TOKEN", "").strip()
        self.followers_actor = (
            followers_actor
            or os.getenv("APIFY_TIKTOK_FOLLOWERS_ACTOR", DEFAULT_FOLLOWERS_ACTOR)
        )
        self.posts_actor = (
            posts_actor
            or os.getenv("APIFY_TIKTOK_POSTS_ACTOR", DEFAULT_POSTS_ACTOR)
        )

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        username = normalize_username(request.username)
        if not username:
            raise ValueError("TikTok username is required.")
        if not self.token:
            raise ValueError(
                "APIFY_TOKEN is not set. Add it to backend/.env before selecting TikTok."
            )

        limit = max(1, min(request.max_profiles, 1000))
        if progress:
            progress(f"Requesting up to {limit} followers via Apify", 0.2)
        follower_items = await self._fetch_followers(username, limit)
        seed = SocialProfile(
            id=f"tt:{username}",
            username=username,
            display_name=username,
            platform=SocialPlatform.TIKTOK,
            profile_url=f"https://www.tiktok.com/@{username}",
            metadata={"role": "Seed", "source": "apify"},
        )

        followers: list[SocialProfile] = []
        connections: list[SocialConnection] = []
        seen = {username.casefold()}
        for item in follower_items:
            profile = _profile_from_item(item)
            if profile is None or profile.username.casefold() in seen:
                continue
            seen.add(profile.username.casefold())
            followers.append(profile)
            connections.append(
                SocialConnection(
                    source_profile_id=profile.id,
                    target_profile_id=seed.id,
                    relation=RelationType.FOLLOWS,
                )
            )
            if len(followers) >= limit:
                break

        profiles = [seed, *followers]
        hashtag_profiles = profiles[: min(HASHTAG_PROFILE_LIMIT, len(profiles))]
        hashtag_warning = ""
        if progress:
            progress(f"Collecting hashtags from {len(hashtag_profiles)} profiles", 0.7)
        try:
            post_items = await self._fetch_posts(
                [profile.username for profile in hashtag_profiles]
            )
        except Exception as error:
            # Followers remain useful when the separate posts actor is unavailable.
            post_items = []
            hashtag_warning = f" Hashtag enrichment failed: {error}"
        usages = _hashtag_usages(post_items, {profile.username: profile.id for profile in profiles})

        return SocialNetwork(
            network_id=f"tiktok:{username.lower()}",
            seed_username=username,
            platform=SocialPlatform.TIKTOK,
            summary=(
                f"Live TikTok network for @{username}: {len(followers)} visible followers. "
                f"Hashtags from recent posts of {len(hashtag_profiles)} profiles."
                f"{hashtag_warning}"
            ).strip(),
            profiles=profiles,
            connections=connections,
            hashtag_usages=usages,
        )

    async def _fetch_followers(
        self, username: str, limit: int
    ) -> list[dict[str, Any]]:
        return await run_actor(
            self.token,
            self.followers_actor,
            {
                "profiles": [username],
                "mode": "followers",
                "maxItemsPerProfile": limit,
                "includeSourceProfile": True,
                "includeSummary": False,
                "deduplicateWithinProfile": True,
            },
            dataset_limit=limit + 20,
        )

    async def _fetch_posts(self, usernames: list[str]) -> list[dict[str, Any]]:
        if not usernames:
            return []
        return await run_actor(
            self.token,
            self.posts_actor,
            {
                "profiles": usernames,
                "resultsPerPage": POSTS_PER_PROFILE,
                "profileScrapeSections": ["videos"],
                "profileSorting": "latest",
                "excludePinnedPosts": False,
                "shouldDownloadVideos": False,
                "shouldDownloadCovers": False,
                "shouldDownloadAvatars": False,
            },
            dataset_limit=len(usernames) * POSTS_PER_PROFILE + 20,
        )


def _profile_from_item(item: dict[str, Any]) -> SocialProfile | None:
    if item.get("recordType") in {"summary", "error"}:
        return None
    username = _first_str(item, "username", "uniqueId", "userName")
    if not username and isinstance(item.get("data"), dict):
        item = {**item, **item["data"]}
        username = _first_str(item, "username", "uniqueId", "userName")
    if not username:
        return None
    username = normalize_username(username)

    verified = _first_bool(item, "isVerified", "verified")
    private = _first_bool(item, "accountPrivate", "privateAccount", "isPrivate")
    return SocialProfile(
        id=f"tt:{username}",
        username=username,
        display_name=_first_str(item, "displayName", "nickname", "nickName") or username,
        platform=SocialPlatform.TIKTOK,
        bio=_first_str(item, "bio", "signature"),
        avatar_url=_first_str(item, "profilePictureUrl", "avatar", "avatarUrl"),
        profile_url=f"https://www.tiktok.com/@{username}",
        follower_count=_first_int(item, "followersCount", "fans", "followerCount"),
        following_count=_first_int(item, "followingCount", "following"),
        is_verified=verified,
        is_private=private,
        metadata={
            "role": "Verified" if verified else "Person",
            "source": "apify",
        },
    )


def _hashtag_usages(
    posts: list[dict[str, Any]],
    profile_ids: dict[str, str],
) -> list[HashtagUsage]:
    counts: Counter[tuple[str, str]] = Counter()
    casefolded_ids = {username.casefold(): profile_id for username, profile_id in profile_ids.items()}

    for post in posts:
        author = post.get("authorMeta")
        username = ""
        if isinstance(author, dict):
            username = _first_str(author, "name", "username", "uniqueId") or ""
        username = username or _first_str(post, "authorName", "username") or ""
        profile_id = casefolded_ids.get(normalize_username(username).casefold())
        if not profile_id:
            continue

        tags: set[str] = set()
        raw_tags = post.get("hashtags")
        if isinstance(raw_tags, list):
            for raw in raw_tags:
                if isinstance(raw, str):
                    tag = raw
                elif isinstance(raw, dict):
                    tag = _first_str(raw, "name", "hashtagName", "title") or ""
                else:
                    tag = ""
                tag = _normalize_tag(tag)
                if tag:
                    tags.add(tag)

        text = post.get("text")
        if isinstance(text, str):
            tags.update(_normalize_tag(tag) for tag in re.findall(r"#([\w.-]+)", text))
            tags.discard("")

        for tag in tags:
            counts[(profile_id, tag)] += 1

    return [
        HashtagUsage(profile_id=profile_id, hashtag=tag, post_count=count)
        for (profile_id, tag), count in counts.items()
    ]


def _normalize_tag(value: str) -> str:
    return value.strip().lstrip("#").casefold()


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _first_bool(data: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.casefold() in {"true", "1", "yes"}
    return False

