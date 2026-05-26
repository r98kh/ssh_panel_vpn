# Stage 1: Build React Frontend
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build

# Stage 2: Build ShadowLink Go Binaries
FROM golang:1.23-alpine AS shadowlink-build
WORKDIR /build
COPY shadowlink/go.mod shadowlink/go.sum ./
RUN go mod download
COPY shadowlink/ .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" \
    -o /build/dist/shadowlink-server ./cmd/server && \
    CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" \
    -o /build/dist/shadowlink-client ./cmd/client

# Stage 3: Python Application
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /build/dist /app/frontend/dist
COPY --from=shadowlink-build /build/dist/shadowlink-server /usr/local/bin/shadowlink-server
COPY --from=shadowlink-build /build/dist/shadowlink-client /usr/local/bin/shadowlink-client

RUN mkdir -p /app/logs /app/staticfiles

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "sshvpn.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--access-logfile", "-"]
