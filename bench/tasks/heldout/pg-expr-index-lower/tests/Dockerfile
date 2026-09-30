FROM python:3.12.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_URL=postgresql+psycopg://practice:practice-local@postgres:5432/practice
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates git postgresql-client && rm -rf /var/lib/apt/lists/*
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN pip install --no-cache-dir -r /tmp/baseline-requirements.txt "SQLAlchemy==2.0.36" "psycopg[binary]==3.2.3" "Django==5.1.2" "alembic==1.14.0" "pytest==8.3.3" "ruff==0.7.4"
COPY app/ /app/
WORKDIR /app
RUN find /app -type d -exec chmod 755 {} + && find /app -type f -exec chmod 644 {} + && useradd --create-home --uid 1000 --shell /bin/bash agent
RUN rm -rf /app/.git && chown -R root:root /app && chown agent:agent /app/library/models.py && chown root:agent /app/library/schema_migrations && chmod 775 /app/library/schema_migrations
COPY config.json /opt/task/config.json
COPY verify.py create_manifest.py hidden.py test.sh /tests/
RUN python /tests/create_manifest.py && chmod 755 /tests/test.sh
CMD ["sh", "-c", "sleep infinity"]
