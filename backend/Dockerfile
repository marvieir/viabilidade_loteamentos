# Backend FastAPI — Pré-Viabilidade de Loteamento
# shapely/pyproj/lxml vêm por wheel manylinux (GEOS/PROJ/libxml2 embutidos).
# rasterio (Fase 2.2 — área verde) NÃO tem wheel para linux-arm64 → compila do fonte e
# precisa do GDAL + toolchain de build. Instalamos via apt antes do pip.
FROM python:3.11-slim

# ca-certificates: bundle de CAs do sistema (sem ele, TLS p/ api.anthropic.com falha com
# "unable to get local issuer certificate"). update-ca-certificates funde CAs corporativas
# (Fase 1.8) que você monte em /usr/local/share/ca-certificates/ via volume.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        build-essential \
        ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV GDAL_CONFIG=/usr/bin/gdal-config

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# scripts/ — comandos manuais do operador (ex.: seed de admin via scripts/criar_admin.py). NÃO são
# agentes; precisam estar na imagem p/ rodar `podman exec api python -m scripts.<cmd>`.
COPY scripts ./scripts

# Fase 13 (hardening) — roda como usuário NÃO-root (defesa em profundidade).
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8700
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
