FROM node:24-bookworm-slim AS build
ENV CI=1 EXPO_NO_DOTENV=1
WORKDIR /srv
COPY package.json package-lock.json ./
COPY apps/mobile/package.json ./apps/mobile/package.json
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY apps/mobile ./apps/mobile
WORKDIR /srv/apps/mobile
ARG EXPO_PUBLIC_API_URL
ARG EXPO_PUBLIC_SUPABASE_URL
ARG EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY
ARG EXPO_PUBLIC_DEMO_LOGIN_ID
ARG EXPO_PUBLIC_DEMO_PASSWORD
RUN : "${EXPO_PUBLIC_API_URL:?Set EXPO_PUBLIC_API_URL}" \
    && : "${EXPO_PUBLIC_SUPABASE_URL:?Set EXPO_PUBLIC_SUPABASE_URL}" \
    && : "${EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY:?Set EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY}" \
    && npx expo export --platform web

FROM nginxinc/nginx-unprivileged:1.28-alpine AS runtime
COPY apps/mobile/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/apps/mobile/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
