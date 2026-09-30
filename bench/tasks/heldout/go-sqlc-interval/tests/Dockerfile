FROM sqlc/sqlc:1.27.0 AS generator
FROM golang:1.23.2-bookworm
ENV GOFLAGS=-mod=vendor GOPROXY=off GOTOOLCHAIN=local CGO_ENABLED=0
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates git python3 python3-pip postgresql-client && rm -rf /var/lib/apt/lists/*
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/baseline-requirements.txt
COPY --from=generator /workspace/sqlc /usr/local/bin/sqlc
ENV PAYROLL_DATABASE_URL=postgres://payroll:payroll-local@postgres:5432/payroll_dev?sslmode=disable PAYROLL_TEST_DATABASE_URL=postgres://payroll:payroll-local@postgres:5432/payroll_test?sslmode=disable
COPY app/ /app/
WORKDIR /app
RUN rm -rf /app/.git && find /app -type d -exec chmod 755 {} + && find /app -type f -exec chmod 644 {} + && go build ./... && go vet ./... && go test -count=1 -run '^$' ./... && useradd --create-home --uid 1000 --shell /bin/bash agent && chown -R root:root /app && chown agent:agent /app/db/queries/payroll.sql /app/internal/db/payroll.sql.go
COPY config.json /opt/task/config.json
COPY verify.py create_manifest.py hidden_test.go test.sh /tests/
RUN python3 /tests/create_manifest.py && chmod 755 /tests/test.sh
CMD ["sh", "-c", "sleep infinity"]
