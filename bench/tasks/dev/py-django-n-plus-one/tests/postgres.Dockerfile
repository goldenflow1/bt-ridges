FROM postgres:16.4-bookworm

COPY seed.sql /opt/task-seed/seed.sql
COPY postgres-init.sh /docker-entrypoint-initdb.d/10-task-init.sh
RUN chmod 755 /docker-entrypoint-initdb.d/10-task-init.sh \
    && chmod 644 /opt/task-seed/seed.sql
