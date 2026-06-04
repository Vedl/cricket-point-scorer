# Render / HF single-container Reflex app, memory-lean for the 512MB free tier.
# The frontend is COMPILED AT BUILD TIME (plenty of memory) and served as static files
# by Caddy; Reflex runs BACKEND-ONLY at runtime — so the heavy bun/node frontend compile
# never runs in the container, keeping runtime memory ~190MB (no OOM).
FROM python:3.12-slim

# Caddy binary (serves the static frontend + proxies the backend on one port).
COPY --from=caddy:2-alpine /usr/bin/caddy /usr/local/bin/caddy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REFLEX_TELEMETRY_ENABLED=false

RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app

COPY --chown=user:user requirements-hf.txt ./
RUN pip install -r requirements-hf.txt

COPY --chown=user:user . .
RUN chmod +x hf_start.sh && chown -R user:user /app

USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH

# Bake the public URL so the built frontend targets the right backend websocket.
ENV API_URL=https://fantasy-sports-jqux.onrender.com \
    DEPLOY_URL=https://fantasy-sports-jqux.onrender.com \
    CORS_ORIGINS=https://fantasy-sports-jqux.onrender.com
# Compile the frontend NOW (build-time) → static files in .web/build. No runtime compile.
RUN reflex init && reflex export --frontend-only --no-zip

EXPOSE 7860
CMD ["./hf_start.sh"]
