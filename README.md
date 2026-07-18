<div align="center">
  <img src="frontend/public/logo.svg" alt="WormBlazz logo" width="92" />

  <h1>WormBlazz</h1>

  <p>
    <strong>Turn public social data into an explorable connection graph.</strong>
  </p>
  <p>
    A self-hostable social network mapping toolkit for discovering relationships
    between public Instagram and TikTok profiles, mentions, and hashtags.
  </p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=0f172a" alt="React 19" />
    <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker ready" />
    <img src="https://img.shields.io/badge/PRs-welcome-6366F1?style=flat-square" alt="Pull requests welcome" />
  </p>

  <p>
    <a href="#features">Features</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#data-sources">Data sources</a> ·
    <a href="#api">API</a> ·
    <a href="#contributing">Contributing</a>
  </p>
</div>

---

## Why WormBlazz?

Social profiles are more useful when viewed as a network instead of a flat list.
WormBlazz collects publicly available profile signals and transforms them into an
interactive graph where people, creators, brands, and hashtags can be explored
together.

The project is built in the open with a self-hosting-first architecture. It offers
a free local crawler for lightweight discovery, optional Apify integrations for
broader datasets, and a demo mode that works without external credentials.

## Features

- **Interactive social graph** — pan, zoom, filter, select, and inspect connected profiles.
- **Instagram and TikTok** — map public profiles, relationships, mentions, and hashtags.
- **Free local crawling** — run background crawls on your own machine without Apify or login.
- **Optional Apify enrichment** — retrieve broader follower datasets using your own token.
- **Hashtag intelligence** — visualize frequently used hashtags and profile-to-topic edges.
- **Large graph performance** — hybrid React Flow and Canvas rendering keeps 1,000-node graphs responsive.
- **Multiple layouts** — switch between force-directed clusters and hierarchical views.
- **Public/private visibility** — visually distinguish public and unavailable profile data.
- **Deep links** — open social profiles and hashtag pages directly from graph nodes.
- **Persistent cache** — avoid repeating completed crawls and keep data sources isolated.
- **API-first backend** — use the FastAPI endpoints independently of the web interface.
- **Docker ready** — build the frontend and backend into one self-contained service.

## How it works

```text
Public profile / handle
          │
          ▼
┌───────────────────────┐
│ Demo · Local · Apify  │  Data source adapters
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ FastAPI crawl service │  Jobs, normalization, cache
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ Social graph model    │  Profiles, relationships, hashtags
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ React graph explorer  │  React Flow + Canvas rendering
└───────────────────────┘
```

## Quick start

### Docker

The easiest way to run the complete application:

```bash
git clone https://github.com/Wormee-Tech/WormBlazz.git
cd WormBlazz
docker compose up --build
```

Open [http://localhost:5000](http://localhost:5000). Demo and local crawling work
without an Apify token.

### Local development

Requirements: Python 3.11+, Node.js 20+, and npm.

```bash
git clone https://github.com/Wormee-Tech/WormBlazz.git
cd WormBlazz

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn wormblazz.main:app --reload --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Data sources

### Demo

Generates a synthetic network for exploring the interface and testing graph
behavior. Demo handles are intentionally fake.

### Local — free and self-hosted

The local source reads basic public profile metadata with `httpx`, then expands
`@mentions` and `#hashtags` using breadth-first search up to the selected depth.
Jobs run in the background and the frontend displays live progress.

- No Apify account or credits
- No login required for basic public data
- Configurable request delay and profile limit
- Best suited to lightweight discovery and development

Local data is intentionally best-effort. Platforms can rate-limit requests or
change their public page structure, and anonymous access does not expose complete
follower lists.

### Apify — optional broader datasets

Add an Apify token to retrieve larger public follower datasets:

```bash
# backend/.env
APIFY_TOKEN=apify_api_xxx
```

Instagram uses a configurable follower actor. TikTok combines a follower actor
with recent-post enrichment to discover hashtags. Actor identifiers can be
overridden in `backend/.env`.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Common settings:

```dotenv
# Optional: required only for Apify sources
APIFY_TOKEN=

# Local crawler controls
WORMBLAZZ_LOCAL_DELAY=1.5
WORMBLAZZ_LOCAL_MAX_NODES=120

# Runtime
WORMBLAZZ_CACHE_DIR=.cache
WORMBLAZZ_CORS_ORIGINS=http://localhost:5173
```

Keep the local delay polite. Never commit API tokens, cookies, or session values.

## API

FastAPI serves both synchronous crawls and asynchronous local jobs:

```text
GET  /api/health
POST /api/network/crawl
POST /api/network/crawl/background
GET  /api/network/jobs/{jobId}
GET  /api/network/{networkId}/overview
GET  /api/network/{networkId}/graph
GET  /api/network/{networkId}/graph/stats
```

Example crawl request:

```json
{
  "username": "instagram",
  "platform": "Instagram",
  "source": "local",
  "depth": 2,
  "maxProfiles": 1000,
  "forceRefresh": true
}
```

When running the backend directly, interactive API documentation is available at
[http://localhost:8000/docs](http://localhost:8000/docs).

## Tech stack

- **Backend:** Python 3.11+, FastAPI, Pydantic, httpx
- **Frontend:** React 19, TypeScript, Vite
- **Visualization:** React Flow, d3-force, Dagre, HTML Canvas
- **Storage:** disk-backed JSON cache
- **Deployment:** Docker and Docker Compose

## Project structure

```text
WormBlazz/
├── backend/
│   ├── wormblazz/       # API, crawlers, jobs, graph mapping, cache
│   └── tests/           # FastAPI and crawler tests
├── frontend/
│   ├── public/
│   └── src/             # React application and graph components
├── Dockerfile
└── docker-compose.yml
```

## Development checks

```bash
# Backend tests
cd backend
pytest

# Frontend type-check and production build
cd frontend
npm run build
```

## Contributing

WormBlazz is being developed toward a community-driven open-source project.
Contributions of all sizes are welcome:

1. Fork the repository.
2. Create a focused branch: `git checkout -b feat/my-improvement`.
3. Add your change and relevant tests.
4. Run the development checks.
5. Open a pull request with a clear explanation and screenshots for UI changes.

Useful contribution areas include new public data adapters, graph layouts,
performance improvements, tests, documentation, accessibility, and localization.
For larger changes, open an issue first so the approach can be discussed.

## Responsible use

WormBlazz is intended for research, education, and analysis of publicly available
information. Users are responsible for complying with platform terms, applicable
laws, privacy requirements, and rate limits.

- Do not use WormBlazz to access private or restricted data.
- Do not use it to evade authentication, CAPTCHA, or platform security controls.
- Collect only the data you need and protect any exported datasets.
- Respect deletion requests and the privacy of the people represented in a graph.

## License

An open-source license has not yet been added. Until one is selected, the source
code remains under its default copyright protections. A license should be added
before the first official open-source release.

---

<div align="center">
  Built with Python, React, and curiosity about how public networks connect.
  <br />
  <a href="https://github.com/Wormee-Tech/WormBlazz/issues">Report a bug</a>
  ·
  <a href="https://github.com/Wormee-Tech/WormBlazz/issues">Request a feature</a>
</div>
