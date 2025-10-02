# syntax=docker/dockerfile:1
FROM node:20-slim AS deps

WORKDIR /usr/src/app

ENV NODE_ENV=development

COPY package.json ./package.json
COPY tsconfig.base.json ./tsconfig.base.json
COPY common/package.json ./common/package.json
COPY hh-enrich-svc/package.json ./hh-enrich-svc/package.json

RUN npm install --workspaces && npm --prefix hh-enrich-svc install --include=dev --no-audit --no-fund

FROM deps AS build

COPY . ./
COPY hh-enrich-svc/python_runtime/scripts ./scripts
COPY hh-enrich-svc/python_runtime/cloud_run_worker ./cloud_run_worker
RUN npm --prefix common run build \
  && npm --prefix hh-enrich-svc run build \
  && npm prune --workspaces --omit=dev

FROM node:20-slim AS runner

ENV NODE_ENV=production
ENV PORT=8080

WORKDIR /usr/src/app

RUN groupadd --system headhunter && useradd --system --no-create-home --home-dir /usr/src/app --gid headhunter headhunter \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip python3-dev build-essential curl \
  && rm -rf /var/lib/apt/lists/*

COPY hh-enrich-svc/python_runtime/cloud_run_worker/requirements.txt ./cloud_run_worker/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r cloud_run_worker/requirements.txt

COPY --from=build /usr/src/app/package.json ./
COPY --from=build /usr/src/app/node_modules ./node_modules
COPY --from=build /usr/src/app/common/dist ./common/dist
COPY --from=build /usr/src/app/common/package.json ./common/package.json
COPY --from=build /usr/src/app/hh-enrich-svc/dist ./hh-enrich-svc/dist
COPY --from=build /usr/src/app/hh-enrich-svc/package.json ./hh-enrich-svc/package.json
COPY --from=build /usr/src/app/scripts ./scripts
COPY --from=build /usr/src/app/cloud_run_worker ./cloud_run_worker

RUN chown -R headhunter:headhunter /usr/src/app

USER headhunter

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD curl --fail http://127.0.0.1:${PORT}/health || exit 1

EXPOSE 8080

CMD ["node", "hh-enrich-svc/dist/index.js"]
