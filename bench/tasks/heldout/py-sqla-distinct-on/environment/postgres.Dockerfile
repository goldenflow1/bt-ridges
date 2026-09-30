FROM postgres:16.6-bookworm
COPY postgres-init.sh /docker-entrypoint-initdb.d/10-init.sh
RUN chmod 755 /docker-entrypoint-initdb.d/10-init.sh
