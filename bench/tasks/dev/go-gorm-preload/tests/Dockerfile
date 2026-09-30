FROM golang:1.23.2-bookworm

ENV GOFLAGS=-mod=vendor \
    GOPROXY=off \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0 \
    AUDITFEED_DATABASE_URL=postgres://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_dev?sslmode=disable \
    AUDITFEED_TEST_DATABASE_URL=postgres://auditfeed:auditfeed-app-81b04c6e@postgres:5432/auditfeed_test?sslmode=disable

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git postgresql-client python3 \
    && rm -rf /var/lib/apt/lists/*

COPY funcspan/ /opt/task-src/funcspan/
RUN cd /opt/task-src/funcspan \
    && mkdir -p /opt/task \
    && GOFLAGS=-mod=mod go build -o /opt/task/funcspan . \
    && rm -rf /opt/task-src

COPY app/ /app/
WORKDIR /app

RUN rm -rf /app/.git \
    && find /app -type d -exec chmod 755 {} + \
    && find /app -type f -exec chmod 644 {} + \
    && go build ./... \
    && go vet ./... \
    && go test -count=1 -run '^$' ./...

COPY create_source_manifest.py /usr/local/bin/create_source_manifest.py
RUN python3 /usr/local/bin/create_source_manifest.py \
    && rm /usr/local/bin/create_source_manifest.py

RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
    && useradd --home-dir /var/empty --uid 1001 --shell /usr/sbin/nologin grader \
    && chown -R root:root /app \
    && chmod -R go-w /app \
    && chown agent:agent /app/internal/store/report.go \
    && chmod 755 /app

COPY test.sh verify.py report_hidden_test.go /tests/
RUN chmod 755 /tests/test.sh \
    && chmod 444 /tests/verify.py /tests/report_hidden_test.go

CMD ["sh", "-c", "sleep infinity"]
