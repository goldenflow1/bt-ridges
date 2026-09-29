FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TIDEWATER_DATABASE_URL=postgresql+psycopg://tidewater:tidewater-app-5c1e93d7@postgres:5432/tidewater_dev \
    TIDEWATER_TEST_DATABASE_URL=postgresql+psycopg://tidewater:tidewater-app-5c1e93d7@postgres:5432/tidewater_test

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "SQLAlchemy==2.0.36" "psycopg[binary]==3.2.3" "pytest==8.3.3" "ruff==0.7.4"

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
    && chown agent:agent /app/tidewater/reports.py \
    && chmod 755 /app

COPY test.sh verify.py revenue_fanout_hidden_test.py /tests/
RUN chmod 755 /tests/test.sh \
    && chmod 444 /tests/verify.py /tests/revenue_fanout_hidden_test.py

CMD ["sh", "-c", "sleep infinity"]
