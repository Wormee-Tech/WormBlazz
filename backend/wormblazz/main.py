from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .cache import NetworkCache
from .graph import to_graph, to_overview, to_stats
from .jobs import JobManager
from .models import (
    CrawlJob,
    CrawlNetworkRequest,
    CrawlNetworkResponse,
    GraphResponse,
    GraphStatsResponse,
    NetworkOverviewResponse,
    SocialNetwork,
)
from .service import NetworkService

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()


def create_app(
    cache_dir: str | Path | None = None,
    frontend_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="WormBlazz API",
        description="Build interactive graphs from publicly available social profile data.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "WORMBLAZZ_CORS_ORIGINS", "http://localhost:5173"
            ).split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.network_service = NetworkService(NetworkCache(cache_dir))
    app.state.job_manager = JobManager()

    def get_service(request: Request) -> NetworkService:
        return request.app.state.network_service

    def get_jobs(request: Request) -> JobManager:
        return request.app.state.job_manager

    def get_network(network_id: str, service: NetworkService) -> SocialNetwork:
        network = service.get(network_id)
        if network is None:
            raise HTTPException(status_code=404, detail="Network not crawled yet.")
        return network

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/network/crawl", response_model=CrawlNetworkResponse)
    async def crawl_network(
        payload: CrawlNetworkRequest,
        service: NetworkService = Depends(get_service),
    ) -> CrawlNetworkResponse:
        try:
            network = await service.crawl(payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return CrawlNetworkResponse(network_id=network.network_id)

    @app.post("/api/network/crawl/background", response_model=CrawlJob)
    async def crawl_network_background(
        payload: CrawlNetworkRequest,
        service: NetworkService = Depends(get_service),
        jobs: JobManager = Depends(get_jobs),
    ) -> CrawlJob:
        async def run(progress) -> str:
            network = await service.crawl(payload, progress)
            return network.network_id

        return jobs.submit(run)

    @app.get("/api/network/jobs/{job_id}", response_model=CrawlJob)
    def crawl_job(
        job_id: str,
        jobs: JobManager = Depends(get_jobs),
    ) -> CrawlJob:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job

    @app.get(
        "/api/network/{network_id}/overview",
        response_model=NetworkOverviewResponse,
    )
    def network_overview(
        network_id: str,
        service: NetworkService = Depends(get_service),
    ) -> NetworkOverviewResponse:
        return to_overview(get_network(network_id, service))

    @app.get("/api/network/{network_id}/graph", response_model=GraphResponse)
    def network_graph(
        network_id: str,
        service: NetworkService = Depends(get_service),
    ) -> GraphResponse:
        return to_graph(get_network(network_id, service))

    @app.get(
        "/api/network/{network_id}/graph/stats",
        response_model=GraphStatsResponse,
    )
    def network_graph_stats(
        network_id: str,
        service: NetworkService = Depends(get_service),
    ) -> GraphStatsResponse:
        return to_stats(get_network(network_id, service))

    static_root = Path(
        frontend_dir
        or os.getenv("WORMBLAZZ_FRONTEND_DIR", Path(__file__).parents[2] / "frontend" / "dist")
    )
    if static_root.is_dir():
        assets = static_root / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            requested = (static_root / path).resolve()
            root = static_root.resolve()
            if requested.is_relative_to(root) and requested.is_file():
                return FileResponse(requested)
            return FileResponse(static_root / "index.html")

    return app


app = create_app()

