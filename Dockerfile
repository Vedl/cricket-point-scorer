# Render/HF single-container Reflex app. reflex run --env prod serves frontend+backend
# on ONE port (proven to deploy on Render free). The WhoScored scrapers + scikit-learn
# load lazily (only when scoring a match), so they don't add startup memory.
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
RUN reflex init
EXPOSE 7860
CMD ["bash", "/app/hf_start.sh"]
