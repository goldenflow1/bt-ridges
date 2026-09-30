FROM node:20.18.0-bookworm-slim

ENV NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git python3 python3-pip openssl \
    && rm -rf /var/lib/apt/lists/*

# The Ridges miner runtime needs python3 and its baseline packages inside the task environment.
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/baseline-requirements.txt \
    && rm /tmp/baseline-requirements.txt

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} + \
    && npm ci --ignore-scripts \
    && npx tsc --noEmit \
    && userdel --remove node && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && chown -R root:root /app \
    && chown root:agent /app/src \
    && chmod 775 /app/src \
    && chown agent:agent /app/src/reports.ts

CMD ["sh", "-c", "sleep infinity"]
