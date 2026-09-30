FROM node:20.18.0-bookworm-slim
ENV NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates git python3 python3-pip openssl postgresql-client && rm -rf /var/lib/apt/lists/*
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/baseline-requirements.txt
ENV STAGEPASS_DATABASE_URL=postgres://stagepass:stagepass-local@postgres:5432/stagepass_dev?sslmode=disable STAGEPASS_TEST_DATABASE_URL=postgres://stagepass:stagepass-local@postgres:5432/stagepass_test?sslmode=disable
COPY app/ /app/
WORKDIR /app
RUN rm -rf /app/.git && find /app -type d -exec chmod 755 {} + && find /app -type f -exec chmod 644 {} + && npm ci --ignore-scripts && npm run typecheck && userdel --remove node && useradd --create-home --uid 1000 --shell /bin/bash agent && chown -R root:root /app && chown agent:agent /app/src/repositories/events.ts
CMD ["sh", "-c", "sleep infinity"]
