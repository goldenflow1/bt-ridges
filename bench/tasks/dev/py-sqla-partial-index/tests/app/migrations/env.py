import os

from alembic import context
from sqlalchemy import create_engine


def apply(connection):
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get('connection')
if connection is not None:
    apply(connection)
else:
    with create_engine(os.environ['DATABASE_URL']).connect() as connection:
        apply(connection)
