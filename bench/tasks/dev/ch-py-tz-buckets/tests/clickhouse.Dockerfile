FROM clickhouse/clickhouse-server:24.8

COPY clickhouse-init.sh /docker-entrypoint-initdb.d/10-task-init.sh
RUN chmod 755 /docker-entrypoint-initdb.d/10-task-init.sh
