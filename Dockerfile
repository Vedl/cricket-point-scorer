# Render/HF Reflex app, memory-safe for 512MB free. Frontend is COMPILED AT BUILD TIME;
# at runtime `reflex run --backend-only` (no compile spike, ~190MB) serves both the API
# and — via the app's api_transformer — the pre-built static frontend. No Caddy (Render
# blocks it), no nginx, no runtime compile (which OOMed).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 REFLEX_TELEMETRY_ENABLED=false
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
COPY --chown=user:user requirements-hf.txt ./
RUN pip install -r requirements-hf.txt
COPY --chown=user:user . .
RUN chmod +x hf_start.sh && chown -R user:user /app
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
ENV API_URL=https://fantasy-sports-jqux.onrender.com \
    DEPLOY_URL=https://fantasy-sports-jqux.onrender.com \
    CORS_ORIGINS=https://fantasy-sports-jqux.onrender.com \
    REFLEX_TRANSPORT=websocket
# `reflex init` fetches bun's install script from raw.githubusercontent.com, which
# Render's shared build-IP pool intermittently gets 429'd (rate-limited) on. Retry
# with backoff instead of failing the whole build on a transient CDN hiccup.
RUN sh -c ' \
    for i in 1 2 3 4 5; do \
      reflex init && reflex export --frontend-only --no-zip && exit 0; \
      echo "reflex export attempt $i failed, retrying in $((i * 15))s..."; \
      sleep $((i * 15)); \
    done; \
    exit 1'
EXPOSE 7860
CMD ["bash", "/app/hf_start.sh"]
