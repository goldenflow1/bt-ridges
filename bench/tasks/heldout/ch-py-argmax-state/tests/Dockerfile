FROM python:3.12.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git && rm -rf /var/lib/apt/lists/*
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN pip install --no-cache-dir -r /tmp/baseline-requirements.txt "pytest==8.3.3" "ruff==0.7.4"
ENV GRID_CLICKHOUSE_URL=http://clickhouse:8123 GRID_CLICKHOUSE_USER=grid GRID_CLICKHOUSE_PASSWORD=grid-task-local GRID_DATABASE=grid_dev GRID_TEST_DATABASE=grid_test
COPY app/ /app/
WORKDIR /app
RUN rm -rf /app/.git && find /app -type d -exec chmod 755 {} + && find /app -type f -exec chmod 644 {} + && useradd --create-home --uid 1000 --shell /bin/bash agent && chown -R root:root /app && chown agent:agent /app/grid/reports/current.py /app/grid/reports/panel.py /app/grid/reports/history.py
COPY config.json /opt/task/config.json
COPY verify.py create_manifest.py hidden.py test.sh /tests/
RUN python /tests/create_manifest.py && chmod 755 /tests/test.sh
CMD ["sh", "-c", "sleep infinity"]
