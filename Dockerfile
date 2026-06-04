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
    CORS_ORIGINS=https://fantasy-sports-jqux.onrender.com
RUN reflex init && reflex export --frontend-only --no-zip
EXPOSE 7860
CMD ["bash", "/app/hf_start.sh"]
