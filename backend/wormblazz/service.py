from __future__ import annotations

from .cache import NetworkCache
from .crawlers import (
    ProgressCallback,
    SocialNetworkCrawler,
    default_crawlers,
    normalize_username,
)
from .models import CrawlNetworkRequest, CrawlSource, SocialNetwork, SocialPlatform


class NetworkService:
    def __init__(
        self,
        cache: NetworkCache,
        crawlers: dict[tuple[SocialPlatform, CrawlSource], SocialNetworkCrawler]
        | None = None,
    ) -> None:
        self.cache = cache
        self.crawlers = crawlers or default_crawlers()

    @staticmethod
    def network_id_for(request: CrawlNetworkRequest, username: str) -> str:
        base = f"{request.platform.value.lower()}:{username.lower()}"
        if request.platform is SocialPlatform.DEMO or request.source is CrawlSource.APIFY:
            return base
        # Local data differs from Apify data — keep them in separate cache slots.
        return f"{request.platform.value.lower()}:{request.source.value}:{username.lower()}"

    async def crawl(
        self,
        request: CrawlNetworkRequest,
        progress: ProgressCallback | None = None,
    ) -> SocialNetwork:
        username = normalize_username(request.username) or "wormee"
        normalized = request.model_copy(update={"username": username})
        network_id = self.network_id_for(request, username)

        if not request.force_refresh:
            cached = self.cache.get(network_id)
            is_legacy_tiktok_stub = (
                cached
                and request.platform is SocialPlatform.TIKTOK
                and "not configured" in cached.summary.casefold()
            )
            if cached and not is_legacy_tiktok_stub:
                return cached

        crawler: SocialNetworkCrawler | None = self.crawlers.get(
            (request.platform, request.source)
        )
        if crawler is None:
            raise ValueError(
                f"No crawler registered for {request.platform.value} "
                f"({request.source.value})."
            )

        network = await crawler.crawl(normalized, progress)
        network.network_id = network_id
        self.cache.set(network)
        return network

    def get(self, network_id: str) -> SocialNetwork | None:
        return self.cache.get(network_id)

