# Fantasy Auction Platform — single-container Reflex app.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REFLEX_TELEMETRY_ENABLED=false

# Reflex downloads & runs `bun` for the frontend; it needs curl + unzip.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (layer cache).
COPY requirements-app.txt ./
RUN pip install -r requirements-app.txt

# App source.
COPY . .

# Pre-build the frontend at image-build time so the container starts fast and
# does not need to download bun/npm deps at runtime.
RUN reflex init && reflex export --frontend-only --no-zip

# 3000 = web UI, 8000 = backend websocket/event API.
EXPOSE 3000 8000

# Production mode serves the compiled frontend + backend together.
CMD ["reflex", "run", "--env", "prod"]
