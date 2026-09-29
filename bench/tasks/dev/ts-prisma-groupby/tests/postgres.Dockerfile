FROM postgres:16.4-bookworm

COPY postgres-init.sh /docker-entrypoint-initdb.d/10-task-init.sh
RUN chmod 755 /docker-entrypoint-initdb.d/10-task-init.sh
