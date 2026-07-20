# Frontend Next.js — Pré-Viabilidade de Loteamento
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

FROM node:22-slim AS builder
WORKDIR /app
COPY . .
# Blindagem (achado do operador, 2026-07-17): builders com .dockerignore ignorado (podman-remote
# do macOS) podem trazer .next/ e node_modules/ STALE do host — o Next então reaproveita
# prerender velho e a imagem sai com rotas de duas eras (index antigo + loteadores novo).
# Ordem à prova de contrabando: SONDA imprime no log o que o builder recebeu de verdade;
# .next e node_modules do contexto são DESCARTADOS; deps entram só da etapa limpa.
RUN echo "== SONDA: primeira linha da home no contexto ==" \
    && head -1 "app/(site)/page.tsx" \
    && echo "== SONDA: fim ==" \
    && rm -rf .next node_modules
COPY --from=deps /app/node_modules ./node_modules
ARG NEXT_PUBLIC_API_BASE=http://localhost:8700
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
# Login com Google (opcional): o Client ID é PÚBLICO e vira parte do bundle no build.
# Vazio → o botão do Google simplesmente não aparece.
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID=
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# Servidor standalone do Next: respeita PORT/HOSTNAME (convenção do projeto: > 3700).
ENV PORT=3700
ENV HOSTNAME=0.0.0.0
# Copia só o necessário (sem o node_modules inteiro): servidor traçado + estáticos.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# Fase 13 (hardening) — roda como usuário NÃO-root (a imagem node já traz o usuário `node`).
USER node
EXPOSE 3700
CMD ["node", "server.js"]
