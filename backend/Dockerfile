# Backend FastAPI — Pré-Viabilidade de Loteamento
# Os wheels manylinux de shapely/pyproj/lxml já trazem GEOS, PROJ e libxml2
# embutidos — não é preciso instalar libs de sistema via apt.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8700
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8700"]
