FROM golang:1.23.2-bookworm
ENV GOFLAGS=-mod=vendor GOPROXY=off GOTOOLCHAIN=local CGO_ENABLED=0
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates git python3 python3-pip && rm -rf /var/lib/apt/lists/*
COPY baseline-requirements.txt /tmp/baseline-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/baseline-requirements.txt
ENV BUILDVAULT_DATABASE=buildvault_dev BUILDVAULT_TEST_DATABASE=buildvault_test
COPY app/ /app/
WORKDIR /app
RUN rm -rf /app/.git && find /app -type d -exec chmod 755 {} + && find /app -type f -exec chmod 644 {} + && go build ./... && go vet ./... && go test -count=1 -run '^$' ./... && useradd --create-home --uid 1000 --shell /bin/bash agent && chown -R root:root /app && chown root:agent /app/migrations && chmod 775 /app/migrations
CMD ["sh", "-c", "sleep infinity"]
