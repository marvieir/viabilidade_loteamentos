# CLAUDE.md — Convenções do projeto

> Leia este arquivo e o `ARCHITECTURE.md` no início de cada sessão.
> A spec da fase atual está em `docs/fase-N-*.md`. Esses três são a fonte de verdade.

## O projeto
Ferramenta de **pré-viabilidade de loteamento**: recebe o KMZ de uma gleba e produz
uma análise de triagem (não decide aprovação municipal). Backend FastAPI + frontend
Next.js. Detalhes e parâmetros legais em `ARCHITECTURE.md`.

## Regras inegociáveis (quebrar isto é regressão)
1. **Cálculo numérico só no backend Python.** Nunca no frontend, nunca via LLM.
2. **Frontend só renderiza JSON.** Proibido geo-matemática em JavaScript.
3. **Todo número devolvido carrega proveniência** (fonte legal, perfil, data de referência).
4. **Determinismo:** mesma entrada → mesma saída, sempre.
5. **Não inventar dado de jurisdição ausente.** Sem perfil municipal → degradar para
   nível federal e rotular cobertura (`BASE_FEDERAL` / `PARCIAL_UF` / `COMPLETA`).

## Convenção de portas (este projeto)
- Frontend: porta **> 3700** (default `3700`).
- Backend: porta **> 8700** (default `8700`).

## Backend
- Python 3.11+, FastAPI, Pydantic v2.
- Geo: `shapely` 2.x, `pyproj`, `rasterio`. Área/perímetro por **cálculo geodésico**
  (`pyproj.Geod`), não por área em graus.
- Cada dimensão de viabilidade = **um router/endpoint** isolado.
- Testes: `pytest`. Toda fase tem testes contra os **valores-ouro** da sua spec.
  Não considere a fase pronta sem esses testes passando.
- Estrutura sugerida:
  ```
  backend/
    app/
      main.py
      routers/        # um arquivo por dimensão
      core/           # parse KMZ, geometria, jurisdição (motor determinístico)
      models/         # schemas Pydantic (contratos de API)
      perfis/         # camadas federal/estadual/municipal
    tests/            # valores-ouro por fase
  ```

## Frontend
- Next.js (App Router), TypeScript, Tailwind, **shadcn/ui** para componentes (cards,
  tabs, dialog, table, badge).
- Mapa: **react-leaflet**. Polígono e buffers vêm como GeoJSON do backend;
  camadas oficiais entram como `TileLayer.WMS`.
- Cada dimensão = **um card** que chama seu endpoint sob demanda.
- O front nunca recalcula nem reformata números — exibe o que o backend mandou,
  incluindo a proveniência.
- Estrutura sugerida:
  ```
  frontend/
    app/
    components/
      mapa/           # MapaLeaflet, camadas WMS, render do polígono
      cards/          # um card por dimensão
      ui/             # shadcn
    lib/api.ts        # cliente do backend
  ```

## Disciplina de implementação
- **Incrementos pequenos e testáveis.** Se quebrar, volte ao último estado estável (git).
- **Sem over-engineering.** A spec fixa contrato e restrições; o resto é latitude sua.
  Não adicione abstração, fila, cache ou microsserviço que a fase não pediu.
- Pense na solução completa mais simples antes de codar. Nada de solução parcial que gere retrabalho.
- Não tire conclusão sem ter a informação. Em dúvida de **design/contrato**, pare e
  pergunte (a dúvida volta para a sessão de especificação, não se resolve chutando).

## Deploy
- Docker Compose com dois serviços: `api` (FastAPI) e `web` (Next.js). Alvo: Lightsail.
