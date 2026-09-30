import pytest
from grid.client import ClickHouse
from grid.schema import create_schema


@pytest.fixture(scope='session')
def client():
    client=ClickHouse.from_env('GRID_TEST_DATABASE')
    create_schema(client)
    return client


@pytest.fixture
def ch(client):
    client.command('TRUNCATE TABLE meter_events')
    return client
