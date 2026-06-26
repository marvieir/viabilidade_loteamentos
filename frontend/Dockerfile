# Frontend Next.js — Pré-Viabilidade de Loteamento
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE=http://localhost:8700
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
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
