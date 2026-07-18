# WormBlazz architecture

## Request flow

```text
React UI
  └─ /api/network/*
      └─ FastAPI routes
          └─ NetworkService
              ├─ JSON NetworkCache
              └─ platform crawler
                  ├─ DemoCrawler
                  ├─ InstagramCrawler (approved API adapter stub)
                  └─ TikTokCrawler (approved API adapter stub)
```

The service returns a platform-neutral `SocialNetwork`. `graph.py` converts that model
to the `nodes` and `edges` contract consumed by React Flow.

## Backend

- `backend/wormblazz/main.py`: application factory, routes, CORS, static frontend
- `backend/wormblazz/models.py`: Pydantic request, domain, and response models
- `backend/wormblazz/crawlers.py`: crawler interface and platform implementations
- `backend/wormblazz/service.py`: cache lookup and crawler dispatch
- `backend/wormblazz/cache.py`: atomic, persistent JSON cache
- `backend/wormblazz/graph.py`: graph, overview, and statistics projections

API responses use camelCase aliases to match TypeScript conventions.

## Frontend

- `frontend/src/App.tsx`: network form, loading, error, and tab state
- `frontend/src/networkApi.ts`: typed API client
- `frontend/src/components/ArchitectureGraph.tsx`: React Flow rendering
- `frontend/src/utils/layoutGraph.ts`: Dagre hierarchical layout

Vite proxies `/api` to FastAPI on port 8000 during development. In production,
FastAPI serves the compiled React app.

## Data boundaries

Only publicly available data exposed through approved platform APIs belongs in the
system. Platform adapters must preserve rate limits and access controls. The app does
not include browser automation, login bypasses, CAPTCHA handling, or private-account
collection.
