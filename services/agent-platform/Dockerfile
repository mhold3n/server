# Monorepo: @server/open-multi-agent + @server/agent-platform-server
FROM node:22-bookworm-slim AS builder

WORKDIR /build

COPY package.json package-lock.json ./
COPY open-multi-agent ./open-multi-agent
COPY server ./server

RUN npm ci
RUN npm run build -w @server/open-multi-agent && npm run build -w @server/agent-platform-server

FROM node:22-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/package.json /build/package-lock.json ./
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/open-multi-agent ./open-multi-agent
COPY --from=builder /build/server ./server

WORKDIR /app/server

ENV NODE_ENV=production
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["node", "dist/server.js"]
