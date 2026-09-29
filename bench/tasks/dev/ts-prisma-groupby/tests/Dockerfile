FROM node:20.18.0-bookworm-slim

ENV CHECKPOINT_DISABLE=1 \
    PRISMA_HIDE_UPDATE_MESSAGE=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    COURSEBOARD_DATABASE_URL=postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_dev \
    COURSEBOARD_TEST_DATABASE_URL=postgresql://courseboard:courseboard-app-2a7d5e90@postgres:5432/courseboard_test

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git openssl postgresql-client python3 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/task/tsparser \
    && npm install --prefix /opt/task/tsparser --no-save typescript@5.6.3 \
    && chmod -R go-w /opt/task
COPY tsspan.cjs /opt/task/tsspan.cjs

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} + \
    && npm ci \
    && npx prisma generate \
    && npx tsc --noEmit

COPY create_source_manifest.py /usr/local/bin/create_source_manifest.py
RUN python3 /usr/local/bin/create_source_manifest.py \
    && rm /usr/local/bin/create_source_manifest.py

RUN userdel --remove node && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && useradd --home-dir /var/empty --uid 1001 --shell /usr/sbin/nologin grader \
    && chown -R root:root /app \
    && chmod -R go-w /app \
    && chown agent:agent /app/src/reports.ts \
    && chmod 755 /app

COPY test.sh verify.py completion_rate_hidden.test.ts /tests/
RUN chmod 755 /tests/test.sh \
    && chmod 444 /tests/verify.py /tests/completion_rate_hidden.test.ts /opt/task/tsspan.cjs

CMD ["sh", "-c", "sleep infinity"]
