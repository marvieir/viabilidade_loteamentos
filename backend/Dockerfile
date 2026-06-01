# Backend FastAPI — Pré-Viabilidade de Loteamento
FROM python:3.11-slim

# Dependências de sistema para shapely/pyproj/lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev \
    proj-bin \
    libproj-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8700
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
