import pytest

from app.db import engine


@pytest.fixture
def conn():
    with engine.connect() as connection:
        transaction = connection.begin()
        for name in ['jobs']:
            connection.exec_driver_sql('TRUNCATE ' + name + ' RESTART IDENTITY CASCADE')
        yield connection
        transaction.rollback()


@pytest.fixture
def migration(conn):
    from alembic import command
    from alembic.config import Config
    config = Config('alembic.ini')
    config.attributes['connection'] = conn
    class Runner:
        def upgrade(self):
            command.upgrade(config, 'head')
        def downgrade(self):
            command.downgrade(config, 'base')
    return Runner()
