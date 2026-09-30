import pytest
from observatory.chclient import ClickHouse
from observatory.schema import TABLES, create_schema

@pytest.fixture(scope="session")
def client():
    client = ClickHouse.from_env("METERLINE_TEST_DATABASE")
    create_schema(client)
    return client

@pytest.fixture
def ch(client):
    for table in TABLES:
        client.command(f"TRUNCATE TABLE {table}")
    return client
