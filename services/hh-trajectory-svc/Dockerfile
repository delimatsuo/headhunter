# syntax=docker/dockerfile:1
FROM node:20-slim AS deps

WORKDIR /usr/src/app

ENV NODE_ENV=development

# Copy workspace manifests first to leverage Docker layer caching.
COPY package.json tsconfig.base.json ./
COPY common/package.json ./common/
COPY hh-trajectory-svc/package.json ./hh-trajectory-svc/

RUN npm install --workspaces && npm --prefix hh-trajectory-svc install --include=dev --no-audit --no-fund

FROM deps AS build

COPY . .
RUN npm --prefix common run build \
  && npm --prefix hh-trajectory-svc run build \
  && npm prune --workspaces --omit=dev

FROM node:20-slim AS runner

ENV NODE_ENV=production
ENV PORT=7109

WORKDIR /usr/src/app

RUN groupadd --system headhunter && useradd --system --no-create-home --home-dir /usr/src/app --gid headhunter headhunter \
  && apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/src/app/package.json ./
COPY --from=build /usr/src/app/node_modules ./node_modules
COPY --from=build /usr/src/app/common/dist ./common/dist
COPY --from=build /usr/src/app/common/package.json ./common/package.json
COPY --from=build /usr/src/app/hh-trajectory-svc/dist ./hh-trajectory-svc/dist
COPY --from=build /usr/src/app/hh-trajectory-svc/package.json ./hh-trajectory-svc/package.json

# Create models directory for ONNX model (will be mounted or copied separately)
RUN mkdir -p /usr/src/app/models && chown -R headhunter:headhunter /usr/src/app

USER headhunter

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD curl --fail http://127.0.0.1:${PORT}/health || exit 1

EXPOSE 7109

CMD ["node", "hh-trajectory-svc/dist/index.js"]
