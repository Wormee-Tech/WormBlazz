from __future__ import annotations

import os
from typing import Any

import httpx

from .crawlers import ProgressCallback, SocialNetworkCrawler, normalize_username
from .models import (
    CrawlNetworkRequest,
    RelationType,
    SocialConnection,
    SocialNetwork,
    SocialPlatform,
    SocialProfile,
)

DEFAULT_ACTOR = "datadoping~instagram-followers-scraper"
APIFY_BASE = "https://api.apify.com/v2"


class InstagramApifyCrawler(SocialNetworkCrawler):
    """
    Live Instagram follower graph via Apify (commercial data provider).

    Set APIFY_TOKEN in the environment. Optional:
      APIFY_INSTAGRAM_ACTOR  (default: datadoping~instagram-followers-scraper)
    """

    platform = SocialPlatform.INSTAGRAM

    def __init__(
        self,
        token: str | None = None,
        actor_id: str | None = None,
        timeout_seconds: float = 600.0,
    ) -> None:
        self.token = token if token is not None else os.getenv("APIFY_TOKEN", "").strip()
        self.actor_id = (
            actor_id
            or os.getenv("APIFY_INSTAGRAM_ACTOR", DEFAULT_ACTOR).strip()
            or DEFAULT_ACTOR
        )
        self.timeout_seconds = timeout_seconds

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        username = normalize_username(request.username)
        if not username:
            raise ValueError("Instagram username is required.")
        if not self.token:
            raise ValueError(
                "APIFY_TOKEN is not set. Create a free token at https://console.apify.com/account/integrations "
                "and export APIFY_TOKEN before selecting the Instagram platform."
            )

        limit = max(1, min(request.max_profiles, 1000))
        if progress:
            progress(f"Requesting up to {limit} followers via Apify", 0.2)
        items = await self._fetch_followers(username, limit)

        seed = SocialProfile(
            id=f"ig:{username}",
            username=username,
            display_name=username,
            platform=SocialPlatform.INSTAGRAM,
            profile_url=f"https://www.instagram.com/{username}/",
            is_verified=False,
            is_private=False,
            metadata={"role": "Seed", "source": "apify"},
        )

        followers: list[SocialProfile] = []
        connections: list[SocialConnection] = []
        seen: set[str] = {username.casefold()}

        for item in items:
            follower = _profile_from_item(item)
            if follower is None:
                continue
            if follower.username.casefold() in seen:
                continue
            seen.add(follower.username.casefold())
            followers.append(follower)
            connections.append(
                SocialConnection(
                    source_profile_id=follower.id,
                    target_profile_id=seed.id,
                    relation=RelationType.FOLLOWS,
                    weight=1,
                )
            )
            if len(followers) >= limit:
                break

        profiles = [seed, *followers]
        return SocialNetwork(
            network_id=f"instagram:{username.lower()}",
            seed_username=username,
            platform=SocialPlatform.INSTAGRAM,
            summary=(
                f"Live Instagram network for @{username}: {len(followers)} public followers "
                f"(capped at {limit}) via Apify actor `{self.actor_id}`."
            ),
            profiles=profiles,
            connections=connections,
        )

    async def _fetch_followers(self, username: str, limit: int) -> list[dict[str, Any]]:
        run_input = {
            "usernames": [username],
            "max_count": limit,
        }
        # Compatible alternate keys used by other Instagram follower actors.
        run_input_alt_keys = {
            "username": [username],
            "maxItem": limit,
            "maxResults": limit,
            "resultsLimit": limit,
        }
        payload = {**run_input, **run_input_alt_keys}

        headers = {"Authorization": f"Bearer {self.token}"}
        timeout = httpx.Timeout(self.timeout_seconds, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            start = await client.post(
                f"{APIFY_BASE}/acts/{self.actor_id}/runs",
                params={"waitForFinish": 120},
                json=payload,
            )
            if start.status_code >= 400:
                detail = start.text[:500]
                raise ValueError(
                    f"Apify actor `{self.actor_id}` failed ({start.status_code}): {detail}"
                )

            run = start.json().get("data") or {}
            run_id = run.get("id")
            status = run.get("status")
            if not run_id:
                raise ValueError("Apify did not return a run id.")

            # Poll if the short wait did not finish.
            while status in {"READY", "RUNNING"}:
                await _sleep(3)
                poll = await client.get(f"{APIFY_BASE}/actor-runs/{run_id}")
                poll.raise_for_status()
                run = poll.json().get("data") or {}
                status = run.get("status")

            if status != "SUCCEEDED":
                raise ValueError(
                    f"Apify run `{run_id}` ended with status `{status}`. "
                    "Check the actor logs in the Apify console."
                )

            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                raise ValueError("Apify run completed without a dataset.")

            items_response = await client.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items",
                params={"format": "json", "clean": "true", "limit": limit},
            )
            items_response.raise_for_status()
            items = items_response.json()
            if not isinstance(items, list):
                raise ValueError("Unexpected Apify dataset payload.")
            return items


def _profile_from_item(item: dict[str, Any]) -> SocialProfile | None:
    username = _first_str(
        item,
        "username",
        "userName",
        "user_name",
        "handle",
        "pk",
    )
    # Some actors nest the user object.
    user = item.get("user") if isinstance(item.get("user"), dict) else None
    if not username and user:
        username = _first_str(user, "username", "userName", "pk")
        item = {**item, **user}

    if not username or not isinstance(username, str):
        return None
    username = normalize_username(username)
    if not username:
        return None

    display = _first_str(item, "full_name", "fullName", "name", "fullName") or username
    bio = _first_str(item, "biography", "bio", "description")
    avatar = _first_str(
        item,
        "profile_pic_url",
        "profilePicUrl",
        "profile_pic_url_hd",
        "profilePicUrlHD",
    )
    verified = bool(
        item.get("is_verified")
        or item.get("isVerified")
        or item.get("verified")
        or False
    )
    followers = _first_int(item, "follower_count", "followersCount", "followers")
    following = _first_int(item, "following_count", "followingCount", "followsCount")
    is_private = bool(
        item.get("is_private")
        or item.get("isPrivate")
        or item.get("private")
        or item.get("is_private_account")
        or False
    )

    return SocialProfile(
        id=f"ig:{username}",
        username=username,
        display_name=display,
        platform=SocialPlatform.INSTAGRAM,
        bio=bio,
        avatar_url=avatar,
        profile_url=f"https://www.instagram.com/{username}/",
        follower_count=followers,
        following_count=following,
        is_verified=verified,
        is_private=is_private,
        metadata={
            "role": "Verified" if verified else "Person",
            "source": "apify",
        },
    )


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
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
