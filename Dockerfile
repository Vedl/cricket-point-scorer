# Hugging Face Spaces (Docker SDK) — single-container Reflex app with 16 GB RAM.
# HF exposes ONE port (7860); Caddy fronts Reflex's frontend (3000) + backend (8000).
FROM python:3.12-slim

# Caddy binary (single-port reverse proxy) — copied from the official image.
COPY --from=caddy:2-alpine /usr/bin/caddy /usr/local/bin/caddy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REFLEX_TELEMETRY_ENABLED=false

# Reflex downloads & runs `bun` for the frontend build; it needs curl + unzip.
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && \
    rm -rf /var/lib/apt/lists/*

# HF runs containers as a non-root user (uid 1000); give it a writable home/app.
RUN useradd -m -u 1000 user
WORKDIR /app

# Python deps first (layer cache).
COPY --chown=user:user requirements-app.txt ./
RUN pip install -r requirements-app.txt

# App source.
COPY --chown=user:user . .
RUN chmod +x hf_start.sh && chown -R user:user /app

USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH

# Pre-download bun / initialise reflex at build time so container start is faster.
RUN reflex init

EXPOSE 7860
CMD ["./hf_start.sh"]
