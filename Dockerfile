# Hugging Face Spaces (Docker SDK) — single-container Reflex app with 16 GB RAM.
# Reflex 0.9 prod serves frontend + backend on ONE port, so it runs directly on HF's
# port 7860 (no reverse proxy needed).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REFLEX_TELEMETRY_ENABLED=false

# Reflex downloads & runs `bun` for the frontend build; it needs curl + unzip.
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && \
    rm -rf /var/lib/apt/lists/*

# HF runs containers as a non-root user (uid 1000); give it a writable home/app.
RUN useradd -m -u 1000 user
WORKDIR /app

# Python deps first (layer cache). Use the LEAN HF manifest (no browser-impersonation
# scrapers — HF's abuse scanner flags those and pauses the Space).
COPY --chown=user:user requirements-hf.txt ./
RUN pip install -r requirements-hf.txt

# App source.
COPY --chown=user:user . .
RUN chmod +x hf_start.sh && chown -R user:user /app

USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH

# Pre-download bun / initialise reflex at build time so container start is faster.
RUN reflex init

EXPOSE 7860
CMD ["./hf_start.sh"]
