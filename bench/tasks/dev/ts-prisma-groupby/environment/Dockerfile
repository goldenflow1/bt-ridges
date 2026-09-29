FROM node:20.18.0-bookworm-slim

ENV CHECKPOINT_DISABLE=1 \
    PRISMA_HIDE_UPDATE_MESSAGE=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    COURSEBOARD_DATABASE_URL=postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_dev \
    COURSEBOARD_TEST_DATABASE_URL=postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_test

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git openssl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} + \
    && npm ci \
    && npx prisma generate \
    && npx tsc --noEmit \
    && userdel --remove node && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && chown -R root:root /app \
    && chown root:agent /app/src \
    && chmod 775 /app/src \
    && chown agent:agent /app/src/reports.ts

CMD ["sh", "-c", "sleep infinity"]
