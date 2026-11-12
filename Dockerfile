# ---- stage 1: build the React frontend -------------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- stage 2: Python API + built frontend (one deployable image) -------------------------------------------------
FROM python:3.12-slim
ARG INSTALL_BGE=false
# Hugging Face Spaces runs containers as UID 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY requirements.txt requirements-bge.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$INSTALL_BGE" = "true" ]; then pip install --no-cache-dir -r requirements-bge.txt; fi
COPY --chown=user:user vaultgraph ./vaultgraph
COPY --from=web --chown=user:user /web/dist ./frontend/dist
USER user
# ENV=production => the app refuses to start without a strong JWT_SECRET (set it as a Space secret / env var).
ENV ENV=production PORT=7860 VAULTGRAPH_DB=/tmp/vaultgraph.db FRONTEND_DIST=/home/user/app/frontend/dist PYTHONUNBUFFERED=1
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"7860\")}/health')"
# --proxy-headers: behind the Hugging Face proxy the real client IP arrives in X-Forwarded-For (needed for per-IP rate limits).
CMD ["sh", "-c", "exec uvicorn vaultgraph.api:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
