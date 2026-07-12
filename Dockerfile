# syntax=docker/dockerfile:1.7

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=17600 \
    SERVE_FRONTEND=true \
    FRONTEND_BUILD_DIR=/app/frontend/build \
    LAN_MODE=true \
    REQUIRE_AUTH=true \
    TELEMETRY_SCOPE=container \
    CAPABILITIES_MODE=safe_runtime

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY capabilities/ /app/capabilities/
COPY --from=frontend-build /build/frontend/build /app/frontend/build

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin lcc \
    && mkdir -p /app/backend/app/data \
    && chown -R lcc:lcc /app/backend/app/data

USER 10001:10001
EXPOSE 17600
VOLUME ["/app/backend/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; r=urllib.request.Request('http://127.0.0.1:17600/api/health',headers={'X-LCC-API-Key':os.environ.get('LCC_API_KEY','')}); urllib.request.urlopen(r,timeout=3)"

CMD ["python", "-m", "app.run"]
