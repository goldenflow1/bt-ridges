import pytest

from app.db import engine


@pytest.fixture
def conn():
    with engine.connect() as connection:
        transaction = connection.begin()
        for name in ['events']:
            connection.exec_driver_sql('TRUNCATE ' + name + ' RESTART IDENTITY CASCADE')
        yield connection
        transaction.rollback()
