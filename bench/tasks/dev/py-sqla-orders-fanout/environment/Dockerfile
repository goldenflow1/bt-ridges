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
    && find /app -type f -exec chmod 644 {} + \
    && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && chown -R root:root /app \
    && chown root:agent /app/tidewater \
    && chmod 775 /app/tidewater \
    && chown agent:agent /app/tidewater/reports.py

CMD ["sh", "-c", "sleep infinity"]
