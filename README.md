# Pré-Viabilidade de Loteamento

Ferramenta de **triagem** (pré-viabilidade) de áreas de loteamento: recebe o KMZ de
uma gleba e produz uma análise determinística — **não decide aprovação municipal**.

> Fonte da verdade: [`CLAUDE.md`](./CLAUDE.md), [`ARCHITECTURE.md`](./ARCHITECTURE.md)
> e a spec da fase atual em [`docs/`](./docs).

## Estado: Fase 1 — Casca + Motor de Aproveitamento

- Upload de KMZ → polígono (GeoJSON), área e perímetro **geodésicos** (`pyproj.Geod`).
- Resolvedor de jurisdição com **degradação graciosa** (`BASE_FEDERAL` quando não há
  perfil municipal — sem inventar dado ausente).
- Motor de **aproveitamento** por modalidade: desmembramento + loteamento nas três
  bases de doação (total / líquida / combinada), cada número com **proveniência**.
- Frontend Next.js: upload, mapa Leaflet, card de aproveitamento, badge de cobertura.
  O front **nunca calcula** — só renderiza o JSON do backend.

## Portas (convenção do projeto)
- Backend FastAPI: **8700**
- Frontend Next.js: **3700**

## Rodar com Compose (Podman ou Docker)

O `docker-compose.yml` é agnóstico de engine — funciona com `podman-compose` ou `docker compose`.

```bash
# Podman
podman-compose up --build

# Docker (alternativa)
docker compose up --build

# web  → http://localhost:3700
# api  → http://localhost:8700  (docs em /docs)
```

## Rodar local (dev)

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # variáveis (malha, ambiental, área verde) — edite se quiser
uvicorn app.main:app --reload --port 8700 --env-file .env
pytest            # valores-ouro das fases
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE=http://localhost:8700
npm run dev                  # http://localhost:3700
```

## Testar a demo
Há um KMZ de exemplo em [`samples/gleba-exemplo.kmz`](./samples) (~5 ha perto de
São Roque/SP). Suba-o pela interface ou via API:

```bash
curl -X POST http://localhost:8700/api/analises \
  -F "kmz=@samples/gleba-exemplo.kmz"
```

## Critérios de aceite (Fase 1)
Cobertos por `pytest` em `backend/tests/`:
1. Área geodésica ±0,5% (vs. UTM) — não área em graus.
2. Bases de doação (Aula 09): `total` 57,0%/142 · `liquida` 61,6%/154 · `combinada` 65,0%/162.
3. Desmembramento (0,74) com proveniência "não é exigência legal".
4. Multi-polígono → usa o maior e registra aviso.
5. Geometria inválida → 422.
6. Degradação graciosa → `BASE_FEDERAL` declarando o que não foi considerado.
7. Determinismo → mesma entrada, mesma saída.
