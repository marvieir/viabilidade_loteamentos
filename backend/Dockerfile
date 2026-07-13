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

# U9 — dwg2dxf (libredwg) p/ ler o LEVANTAMENTO planialtimétrico em DWG DIRETO no servidor (o
# agrimensor entrega DWG; sem isto só DXF). Compila do fonte (arch-agnóstico x86_64/arm64, igual
# ao rasterio) e PURGA o toolchain extra na MESMA layer → imagem enxuta. Binário self-contained
# (--disable-shared) → só o executável fica em /usr/local/bin. `test -f` falha o build alto e claro
# se o binário não sair (em vez de silenciosamente ficar sem conversor).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git autoconf automake libtool \
    && git clone --depth 1 https://github.com/LibreDWG/libredwg.git /tmp/libredwg \
    && cd /tmp/libredwg \
    && sh autogen.sh \
    && ./configure --disable-shared --disable-bindings --disable-dependency-tracking \
    && ( make -j"$(nproc)" || make || true ) \
    && test -f programs/dwg2dxf \
    && install -m 0755 programs/dwg2dxf /usr/local/bin/dwg2dxf \
    && cd / && rm -rf /tmp/libredwg \
    && apt-get purge -y git autoconf automake libtool \
    && rm -rf /var/lib/apt/lists/*
# NOTA: sem `apt-get autoremove` aqui — ele removia o gdal-config (rasterio) junto. Purgamos só as
# ferramentas que ESTE bloco adicionou (git/autotools); as libs do GDAL/build-essential ficam intactas.

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# scripts/ — comandos manuais do operador (ex.: seed de admin via scripts/criar_admin.py). NÃO são
# agentes; precisam estar na imagem p/ rodar `podman exec api python -m scripts.<cmd>`.
COPY scripts ./scripts

# Fase 13 (hardening) — roda como usuário NÃO-root (defesa em profundidade).
# /data/perfis-municipais é o volume nomeado onde a Fase 1.8 GRAVA os perfis confirmados.
# Criar a pasta na imagem com dono=appuser faz um volume nomeado NOVO herdar esse dono
# (Docker copia dono/permissões do diretório da imagem para o volume vazio na 1ª montagem);
# sem isso o volume nasce root e o appuser leva PermissionError ao salvar o perfil.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /data/perfis-municipais /data/juridico /data/perfis \
    && chown -R appuser /app /data
USER appuser

EXPOSE 8700
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
