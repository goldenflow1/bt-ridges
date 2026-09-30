import os

import psycopg
import pytest


@pytest.fixture
def conn():
    url = os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://')
    with psycopg.connect(url) as connection:
        connection.execute('TRUNCATE bookings, departments RESTART IDENTITY CASCADE')
        yield connection
        connection.rollback()
