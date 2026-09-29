FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=pantry_site.settings \
    PANTRY_DB_HOST=postgres \
    PANTRY_DB_NAME=pantry_dev \
    PANTRY_DB_USER=pantry \
    PANTRY_DB_PASSWORD=pantry-app-6f3b19d2

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "Django==5.1.2" "psycopg[binary]==3.2.3" "ruff==0.7.4"

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} + \
    && useradd --create-home --uid 1000 --shell /bin/bash agent \
    && chown -R root:root /app \
    && chown root:agent /app/recipes \
    && chmod 775 /app/recipes \
    && chown agent:agent /app/recipes/views.py /app/recipes/serializers.py /app/recipes/models.py

CMD ["sh", "-c", "sleep infinity"]
