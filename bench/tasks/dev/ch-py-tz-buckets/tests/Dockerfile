FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    METERLINE_CLICKHOUSE_URL=http://clickhouse:8123 \
    METERLINE_CLICKHOUSE_USER=meterline \
    METERLINE_CLICKHOUSE_PASSWORD=meterline-app-4e2a9c17 \
    METERLINE_DATABASE=meterline_dev \
    METERLINE_TEST_DATABASE=meterline_test

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN pip install --no-cache-dir -r /tmp/baseline-requirements.txt "pytest==8.3.3" "ruff==0.7.4"

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} +

COPY create_source_manifest.py /usr/local/bin/create_source_manifest.py
RUN python /usr/local/bin/create_source_manifest.py \
    && rm /usr/local/bin/create_source_manifest.py

RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
    && useradd --home-dir /var/empty --uid 1001 --shell /usr/sbin/nologin grader \
    && chown -R root:root /app \
    && chmod -R go-w /app \
    && chown agent:agent /app/observatory/report.py \
    && chmod 755 /app

COPY test.sh verify.py report_hidden_test.py /tests/
RUN chmod 755 /tests/test.sh \
    && chmod 444 /tests/verify.py /tests/report_hidden_test.py

CMD ["sh", "-c", "sleep infinity"]
