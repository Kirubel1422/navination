# NaviNation web image. Build context: repository root (pnpm workspace).
FROM node:24.19.0-bookworm-slim AS build
ENV NEXT_TELEMETRY_DISABLED=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /repo

# Install dependencies from the lockfile (cached layer). public/ is needed by msw's postinstall.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY apps/web/public apps/web/public
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web

# NEXT_PUBLIC_* values are compiled into the browser bundle, so they are build arguments.
# The browser calls the API directly, so this must be a URL reachable from the user's browser.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_API_MODE=live
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_API_MODE=$NEXT_PUBLIC_API_MODE
RUN pnpm --filter @navination/web build

FROM node:24.19.0-bookworm-slim
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /repo
COPY --from=build --chown=node:node /repo /repo
# Fetch the pinned pnpm now so the container never downloads it at start-up.
USER node
RUN pnpm --version
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["pnpm", "--filter", "@navination/web", "exec", "next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
