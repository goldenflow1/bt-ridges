import pytest
from freight.db import engine


@pytest.fixture
def conn():
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql('TRUNCATE scans, parcels RESTART IDENTITY CASCADE')
        yield connection
        transaction.rollback()
