# syntax=docker/dockerfile:1
FROM node:20-slim AS deps

WORKDIR /usr/src/app

ENV NODE_ENV=development

COPY package.json tsconfig.base.json ./
COPY common/package.json ./common/
COPY hh-admin-svc/package.json ./hh-admin-svc/

RUN npm install --workspaces && npm --prefix hh-admin-svc install --include=dev --no-audit --no-fund

FROM deps AS build

COPY . .
RUN npm --prefix common run build \
  && npm --prefix hh-admin-svc run build \
  && npm prune --workspaces --omit=dev

FROM node:20-slim AS runner

ENV NODE_ENV=production
ENV PORT=8080

WORKDIR /usr/src/app

RUN groupadd --system headhunter \
  && useradd --system --no-create-home --home-dir /usr/src/app --gid headhunter headhunter \
  && apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/src/app/package.json ./
COPY --from=build /usr/src/app/node_modules ./node_modules
COPY --from=build /usr/src/app/common/dist ./common/dist
COPY --from=build /usr/src/app/common/package.json ./common/package.json
COPY --from=build /usr/src/app/hh-admin-svc/dist ./hh-admin-svc/dist
COPY --from=build /usr/src/app/hh-admin-svc/package.json ./hh-admin-svc/package.json
COPY --from=build /usr/src/app/hh-admin-svc/stubs ./hh-admin-svc/stubs
RUN chown -R headhunter:headhunter /usr/src/app

USER headhunter

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD curl --fail http://127.0.0.1:${PORT}/healthz || exit 1

EXPOSE 8080

CMD ["node", "hh-admin-svc/dist/index.js"]
