# ── Stage 1: Build React frontend ──
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ── Stage 2: Python API runtime ──
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WORMBLAZZ_CACHE_DIR=/app/cache \
    WORMBLAZZ_FRONTEND_DIR=/app/frontend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/wormblazz ./wormblazz
COPY --from=frontend-build /app/frontend/dist ./frontend

RUN mkdir -p /app/cache

EXPOSE 8000
CMD ["sh", "-c", "uvicorn wormblazz.main:app --host 0.0.0.0 --port ${PORT}"]
