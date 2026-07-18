"""
Self-hosted, no-cost social scrapers.

These run in a background job and hit each platform's public web endpoints
directly with httpx — no Apify credits required. They are intentionally
best-effort: polite rate limiting, no CAPTCHA solving, no private accounts.

Instagram note: Meta now serves a login wall to anonymous bots even for public
profiles. Local Instagram works reliably when you set INSTAGRAM_SESSION_ID
(your browser `sessionid` cookie). Without it, the crawler still tries HTML
og:meta / embedded JSON, but often gets blocked.

The graph is built from signals public pages expose:
  * @mentions in bios and captions  -> profile -> profile edges (BFS)
  * #hashtags in bios and captions  -> hashtag usage
  * Instagram "related profiles"    -> Related edges (when the richer payload is available)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import deque
from typing import Any

import httpx

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

_MENTION_RE = re.compile(r"@([A-Za-z0-9_.]{2,30})")
_HASHTAG_RE = re.compile(r"#([A-Za-z0-9_]{2,50})")

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Instagram serves public og:meta to link-preview crawlers (no login) but shows a
# login wall to normal browser UAs. Using a bot UA is the free, no-cookie path.
_PREVIEW_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"


def _local_delay() -> float:
    try:
        return max(0.0, float(os.getenv("WORMBLAZZ_LOCAL_DELAY", "1.5")))
    except ValueError:
        return 1.5


def _local_max_nodes() -> int:
    try:
        return max(1, int(os.getenv("WORMBLAZZ_LOCAL_MAX_NODES", "120")))
    except ValueError:
        return 120


class _LocalCrawlerBase(SocialNetworkCrawler):
    """Shared BFS engine; subclasses provide platform-specific parsing."""

    id_prefix: str
    profile_url_template: str
    hashtag_url_template: str

    def __init__(
        self,
        request_delay: float | None = None,
        max_nodes: int | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.request_delay = _local_delay() if request_delay is None else request_delay
        self.max_nodes = _local_max_nodes() if max_nodes is None else max_nodes
        self.timeout_seconds = timeout_seconds

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        seed = normalize_username(request.username)
        if not seed:
            raise ValueError(f"{self.platform.value} username is required.")

        depth = request.depth
        cap = max(1, min(request.max_profiles, self.max_nodes))

        profiles: dict[str, SocialProfile] = {}
        connections: list[SocialConnection] = []
        connection_keys: set[tuple[str, str, str]] = set()
        hashtags: dict[tuple[str, str], int] = {}
        scraped: set[str] = set()
        blocked: list[str] = []

        def profile_id(username: str) -> str:
            return f"{self.id_prefix}:{username.casefold()}"

        def ensure_stub(username: str) -> SocialProfile | None:
            key = username.casefold()
            if key in profiles:
                return profiles[key]
            if len(profiles) >= cap:
                return None
            stub = SocialProfile(
                id=profile_id(username),
                username=username,
                display_name=username,
                platform=self.platform,
                profile_url=self.profile_url_template.format(username=username),
                metadata={"role": "Person", "source": "local", "status": "mention"},
            )
            profiles[key] = stub
            return stub

        def add_edge(source: str, target: str, relation: RelationType) -> None:
            source_key, target_key = source.casefold(), target.casefold()
            if source_key == target_key:
                return
            if source_key not in profiles or target_key not in profiles:
                return
            key = (source_key, target_key, relation.value)
            if key in connection_keys:
                return
            connection_keys.add(key)
            connections.append(
                SocialConnection(
                    source_profile_id=profile_id(source),
                    target_profile_id=profile_id(target),
                    relation=relation,
                )
            )

        queue: deque[tuple[str, int]] = deque([(seed, 0)])
        enqueued = {seed.casefold()}
        ensure_stub(seed)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=10.0),
            headers=self._headers(),
            follow_redirects=True,
        ) as client:
            first = True
            while queue and len(scraped) < cap:
                username, node_depth = queue.popleft()
                key = username.casefold()
                if key in scraped:
                    continue

                if not first and self.request_delay:
                    await asyncio.sleep(self.request_delay)
                first = False

                try:
                    raw = await self._fetch_profile(client, username)
                except Exception:  # noqa: BLE001 - network failures are non-fatal
                    raw = None

                if raw is None:
                    blocked.append(username)
                    continue

                profile = self._build_profile(username, raw, node_depth)
                profiles[key] = profile
                scraped.add(key)
                if progress:
                    progress(
                        f"Scraped @{username} ({len(scraped)}/{cap})",
                        min(0.95, len(scraped) / cap),
                    )

                text_blob = self._text_signals(raw)
                mentions = {
                    m.casefold()
                    for m in _MENTION_RE.findall(text_blob)
                    if m.casefold() != key
                }
                for tag in _HASHTAG_RE.findall(text_blob):
                    normalized = tag.casefold()
                    slot = (key, normalized)
                    hashtags[slot] = hashtags.get(slot, 0) + 1

                for mention in mentions:
                    if ensure_stub(mention) is not None:
                        add_edge(username, mention, RelationType.MENTIONS)
                        if node_depth < depth and mention not in enqueued:
                            enqueued.add(mention)
                            queue.append((mention, node_depth + 1))

                for related_username in self._related_usernames(raw):
                    if related_username.casefold() == key:
                        continue
                    if ensure_stub(related_username) is not None:
                        add_edge(username, related_username, RelationType.RELATED)
                        if node_depth < depth and related_username.casefold() not in enqueued:
                            enqueued.add(related_username.casefold())
                            queue.append((related_username, node_depth + 1))

        if seed.casefold() not in scraped:
            raise ValueError(
                f"Could not read public data for @{seed} on {self.platform.value}. "
                "The account may be private, rate-limited right now, or the handle is "
                "wrong. Public accounts normally work with no login — try again in a "
                "moment, or use Apify for full follower lists."
            )

        usage_list = [
            HashtagUsage(profile_id=profile_id(username), hashtag=tag, post_count=count)
            for (username, tag), count in hashtags.items()
            if username in profiles
        ]

        note = f" {len(blocked)} profiles were unreadable." if blocked else ""
        return SocialNetwork(
            network_id=f"{self.platform.value.lower()}:local:{seed.lower()}",
            seed_username=seed,
            platform=self.platform,
            summary=(
                f"Local {self.platform.value} crawl for @{seed}: {len(scraped)} profiles "
                f"scraped, {len(connections)} mention/related edges, "
                f"{len({tag for _, tag in hashtags})} hashtags. Free, no Apify.{note}"
            ),
            profiles=list(profiles.values()),
            connections=connections,
            hashtag_usages=usage_list,
        )

    # -- platform hooks ---------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": _BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"}

    async def _fetch_profile(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def _build_profile(
        self, username: str, raw: dict[str, Any], depth: int
    ) -> SocialProfile:
        raise NotImplementedError

    def _text_signals(self, raw: dict[str, Any]) -> str:
        raise NotImplementedError

    def _related_usernames(self, raw: dict[str, Any]) -> list[str]:
        return []


class LocalInstagramCrawler(_LocalCrawlerBase):
    """
    Free, login-free Instagram crawl.

    Instagram shows a login wall to normal browser user-agents, but still serves
    the public og:meta (name, follower/following/post counts, bio, avatar) to
    link-preview crawlers such as facebookexternalhit / Googlebot. We use that
    bot user-agent, so **no cookie or login is needed for public accounts**.

    The bio (from the meta description) supplies @mentions and #hashtags that the
    BFS follows. Optional INSTAGRAM_SESSION_ID unlocks the richer JSON API
    (related profiles, captions) but is never required.
    """

    platform = SocialPlatform.INSTAGRAM
    id_prefix = "ig"
    profile_url_template = "https://www.instagram.com/{username}/"
    hashtag_url_template = "https://www.instagram.com/explore/tags/{username}/"

    IG_APP_ID = "936619743392459"
    PROFILE_ENDPOINT = (
        "https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    )

    def __init__(
        self,
        request_delay: float | None = None,
        max_nodes: int | None = None,
        timeout_seconds: float = 25.0,
        session_id: str | None = None,
        cookies: str | None = None,
    ) -> None:
        super().__init__(request_delay, max_nodes, timeout_seconds)
        self.session_id = (
            session_id
            if session_id is not None
            else os.getenv("INSTAGRAM_SESSION_ID", "").strip()
        )
        self.cookie_header = (
            cookies
            if cookies is not None
            else os.getenv("INSTAGRAM_COOKIES", "").strip()
        )

    def _headers(self) -> dict[str, str]:
        # Preview-bot UA is what makes public data load without a login.
        headers = {
            "User-Agent": _PREVIEW_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        }
        cookie = self._cookie_header()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _cookie_header(self) -> str:
        parts: list[str] = []
        if self.cookie_header:
            parts.append(self.cookie_header.rstrip(";"))
        if self.session_id and "sessionid=" not in (self.cookie_header or "").casefold():
            parts.append(f"sessionid={self.session_id}")
        return "; ".join(parts)

    async def _fetch_profile(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any] | None:
        # Primary: public og:meta via preview-bot UA (no cookie, no login).
        html_user = await self._fetch_from_html(client, username)
        if html_user:
            return html_user

        # Optional richer path only when a session cookie is configured.
        if self.session_id or self.cookie_header:
            api_user = await self._fetch_from_api(client, username)
            if api_user:
                return api_user

        return None

    async def _fetch_from_html(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any] | None:
        response = await client.get(
            f"https://www.instagram.com/{username}/",
            headers=self._headers(),
        )
        if response.status_code != 200:
            return None

        text = response.text
        embedded = _extract_instagram_user_from_scripts(text, username)
        if embedded:
            return embedded

        meta = _parse_html_meta(text)
        title = meta.get("og:title") or ""
        og_description = meta.get("og:description") or ""
        description = meta.get("description") or og_description
        # Login wall: bare "Instagram" title, no profile og tags.
        if not title or username.casefold() not in (
            title + meta.get("og:url", "")
        ).casefold():
            if meta.get("og:type") != "profile":
                return None

        display = _display_name_from_og_title(title, username)
        followers, following = _parse_instagram_og_counts(og_description or description)
        bio = _instagram_bio_from_description(description)
        return {
            "username": username,
            "full_name": display,
            "biography": bio,
            "profile_pic_url": meta.get("og:image"),
            "is_private": False,
            "is_verified": False,
            "edge_followed_by": {"count": followers} if followers is not None else {},
            "edge_follow": {"count": following} if following is not None else {},
            "edge_owner_to_timeline_media": {"edges": []},
            "edge_related_profiles": {"edges": []},
            "_source": "og_meta",
        }

    async def _fetch_from_api(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any] | None:
        csrf = client.cookies.get("csrftoken") or ""
        headers = {
            "User-Agent": _BROWSER_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "X-IG-App-ID": self.IG_APP_ID,
            "X-ASBD-ID": "359341",
            "X-IG-WWW-Claim": "0",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf,
            "Referer": f"https://www.instagram.com/{username}/",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        cookie = self._cookie_header()
        if cookie:
            headers["Cookie"] = cookie

        response = await client.get(
            self.PROFILE_ENDPOINT.format(username=username), headers=headers
        )
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return None
        user = (payload.get("data") or {}).get("user")
        return user if isinstance(user, dict) else None

    def _build_profile(
        self, username: str, raw: dict[str, Any], depth: int
    ) -> SocialProfile:
        verified = bool(raw.get("is_verified"))
        return SocialProfile(
            id=f"ig:{username.casefold()}",
            username=username,
            display_name=raw.get("full_name") or username,
            platform=SocialPlatform.INSTAGRAM,
            bio=raw.get("biography") or None,
            avatar_url=raw.get("profile_pic_url_hd") or raw.get("profile_pic_url"),
            profile_url=self.profile_url_template.format(username=username),
            follower_count=_nested_count(raw, "edge_followed_by")
            or _as_int(raw.get("follower_count")),
            following_count=_nested_count(raw, "edge_follow")
            or _as_int(raw.get("following_count")),
            is_verified=verified,
            is_private=bool(raw.get("is_private")),
            metadata={
                "role": "Verified" if verified else "Person",
                "source": "local",
                "depth": str(depth),
                "parse": str(raw.get("_source") or "api"),
            },
        )

    def _text_signals(self, raw: dict[str, Any]) -> str:
        parts: list[str] = [str(raw.get("biography") or "")]
        media = ((raw.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
        for edge in media:
            node = edge.get("node") if isinstance(edge, dict) else None
            if not isinstance(node, dict):
                continue
            captions = ((node.get("edge_media_to_caption") or {}).get("edges")) or []
            for caption in captions:
                caption_node = caption.get("node") if isinstance(caption, dict) else None
                if isinstance(caption_node, dict) and caption_node.get("text"):
                    parts.append(str(caption_node["text"]))
        return "\n".join(parts)

    def _related_usernames(self, raw: dict[str, Any]) -> list[str]:
        edges = ((raw.get("edge_related_profiles") or {}).get("edges")) or []
        usernames: list[str] = []
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if isinstance(node, dict) and node.get("username"):
                usernames.append(normalize_username(str(node["username"])))
        return usernames


def _parse_html_meta(html: str) -> dict[str, str]:
    import html as htmlmod

    meta: dict[str, str] = {}
    for tag in re.findall(r"<meta\b[^>]*>", html, flags=re.IGNORECASE):
        prop = re.search(r'property=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        name = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        content = re.search(r'content=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
        if not content:
            continue
        key = (prop or name).group(1) if (prop or name) else None
        if key:
            meta[key] = htmlmod.unescape(content.group(1))
    title = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if title:
        meta["title"] = htmlmod.unescape(title.group(1)).strip()
    return meta


def _display_name_from_og_title(title: str, username: str) -> str:
    # "VTV DIGITAL (@vtv24news) • Ảnh và video trên Instagram"
    cleaned = re.sub(r"\s*[•|].*$", "", title).strip()
    cleaned = re.sub(rf"\(@?{re.escape(username)}\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -–—")
    return cleaned or username


def _parse_instagram_og_counts(description: str) -> tuple[int | None, int | None]:
    """Parse '447K followers, 97 following' / Vietnamese equivalents."""

    def parse_num(raw: str) -> int | None:
        value = raw.strip().upper().replace(",", "")
        mult = 1.0
        if value.endswith("K"):
            mult = 1_000.0
            value = value[:-1]
        elif value.endswith("M"):
            mult = 1_000_000.0
            value = value[:-1]
        try:
            return int(float(value) * mult)
        except ValueError:
            return None

    followers = following = None
    match = re.search(
        r"([\d.,]+[KkMm]?)\s*(người theo dõi|Followers)",
        description,
        flags=re.IGNORECASE,
    )
    if match:
        followers = parse_num(match.group(1))
    match = re.search(
        r"([\d.,]+[KkMm]?)\s*(đang theo dõi|Following)",
        description,
        flags=re.IGNORECASE,
    )
    if match:
        following = parse_num(match.group(1))
    return followers, following


def _instagram_bio_from_description(description: str) -> str:
    """
    Extract the bio from Instagram's meta description.

    Format: '447K Followers, 97 Following, 32K Posts - NAME (@user) on
    Instagram: "the bio text with @mentions and #hashtags"'
    """
    match = re.search(r'on Instagram:\s*"?(.*)', description, flags=re.DOTALL)
    if match:
        bio = match.group(1).strip().strip('"').strip()
        # Drop a trailing ellipsis IG adds when the bio is truncated.
        return bio.rstrip(". ").strip() if bio.endswith("...") else bio
    return ""


def _extract_instagram_user_from_scripts(
    html: str, username: str
) -> dict[str, Any] | None:
    """Walk application/json blobs for a user object matching the handle."""
    scripts = re.findall(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    target = username.casefold()
    found: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            handle = obj.get("username") or obj.get("userName")
            if (
                isinstance(handle, str)
                and handle.casefold() == target
                and (
                    "biography" in obj
                    or "full_name" in obj
                    or "edge_followed_by" in obj
                    or "follower_count" in obj
                )
            ):
                found.append(obj)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for script in scripts:
        if target not in script.casefold() and username not in script:
            continue
        try:
            walk(json.loads(script))
        except json.JSONDecodeError:
            continue
        if found:
            best = max(
                found,
                key=lambda item: (
                    1 if item.get("biography") else 0,
                    1 if item.get("edge_followed_by") or item.get("follower_count") else 0,
                    len(item),
                ),
            )
            best = dict(best)
            best["_source"] = "html_json"
            return best
    return None


class LocalTikTokCrawler(_LocalCrawlerBase):
    platform = SocialPlatform.TIKTOK
    id_prefix = "tt"
    profile_url_template = "https://www.tiktok.com/@{username}"
    hashtag_url_template = "https://www.tiktok.com/tag/{username}"

    PROFILE_ENDPOINT = "https://www.tiktok.com/@{username}"
    _REHYDRATION_RE = re.compile(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
        re.DOTALL,
    )

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": _BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def _fetch_profile(
        self, client: httpx.AsyncClient, username: str
    ) -> dict[str, Any] | None:
        response = await client.get(
            self.PROFILE_ENDPOINT.format(username=username), headers=self._headers()
        )
        if response.status_code == 200:
            match = self._REHYDRATION_RE.search(response.text)
            if match:
                try:
                    blob = json.loads(match.group(1))
                except json.JSONDecodeError:
                    blob = None
                if blob:
                    scope = blob.get("__DEFAULT_SCOPE__") or {}
                    detail = scope.get("webapp.user-detail") or {}
                    user_info = detail.get("userInfo")
                    if isinstance(user_info, dict) and user_info.get("user"):
                        return user_info

        # Fallback: public og:meta via preview-bot UA (login-free).
        preview = await client.get(
            self.PROFILE_ENDPOINT.format(username=username),
            headers={
                "User-Agent": _PREVIEW_UA,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        if preview.status_code != 200:
            return None
        meta = _parse_html_meta(preview.text)
        title = meta.get("og:title") or ""
        if not title or username.casefold() not in (
            title + meta.get("og:url", "")
        ).casefold():
            return None
        description = meta.get("og:description") or meta.get("description") or ""
        followers = _parse_tiktok_followers(description)
        return {
            "user": {
                "nickname": _display_name_from_og_title(title, username),
                "signature": _tiktok_bio_from_description(description),
                "avatarLarger": meta.get("og:image"),
                "verified": False,
                "privateAccount": False,
            },
            "stats": {"followerCount": followers} if followers is not None else {},
            "_source": "og_meta",
        }

    def _build_profile(
        self, username: str, raw: dict[str, Any], depth: int
    ) -> SocialProfile:
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        verified = bool(user.get("verified"))
        return SocialProfile(
            id=f"tt:{username.casefold()}",
            username=username,
            display_name=user.get("nickname") or username,
            platform=SocialPlatform.TIKTOK,
            bio=user.get("signature") or None,
            avatar_url=user.get("avatarLarger") or user.get("avatarMedium"),
            profile_url=self.profile_url_template.format(username=username),
            follower_count=_as_int(stats.get("followerCount")),
            following_count=_as_int(stats.get("followingCount")),
            is_verified=verified,
            is_private=bool(user.get("privateAccount")),
            metadata={
                "role": "Verified" if verified else "Person",
                "source": "local",
                "depth": str(depth),
                "parse": str(raw.get("_source") or "rehydration"),
            },
        )

    def _text_signals(self, raw: dict[str, Any]) -> str:
        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        return str(user.get("signature") or "")


def _parse_tiktok_followers(description: str) -> int | None:
    match = re.search(r"([\d.,]+[KkMm]?)\s*Followers", description, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip().upper().replace(",", "")
    mult = 1.0
    if value.endswith("K"):
        mult, value = 1_000.0, value[:-1]
    elif value.endswith("M"):
        mult, value = 1_000_000.0, value[:-1]
    try:
        return int(float(value) * mult)
    except ValueError:
        return None


def _tiktok_bio_from_description(description: str) -> str:
    # "nickname (@user) on TikTok | 1.2M Likes. 340K Followers. <bio>. Watch ..."
    parts = re.split(r"Followers\.\s*", description, maxsplit=1)
    if len(parts) == 2:
        tail = re.split(r"\s*Watch the latest", parts[1])[0]
        return tail.strip(" .")
    return ""


def _nested_count(raw: dict[str, Any], key: str) -> int | None:
    node = raw.get(key)
    if isinstance(node, dict):
        return _as_int(node.get("count"))
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
